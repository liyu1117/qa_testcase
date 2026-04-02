"""豆包 AI HTTP 客户端基类 - 统一封装重试、流式、日志"""

import json
import logging
from typing import AsyncGenerator

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from backend.config import settings

logger = logging.getLogger(__name__)


class DoubaoBaseClient:
    """豆包模型 HTTP 调用抽象基类"""

    def __init__(self, timeout: float = 120.0):
        self.api_key = settings.doubao_api_key
        self.timeout = timeout

    def _build_headers(self) -> dict:
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.HTTPStatusError)),
        reraise=True,
    )
    async def _post_request(self, endpoint: str, payload: dict) -> dict:
        """带重试的 HTTP POST 请求"""
        logger.info(f"AI请求: {endpoint}, model={payload.get('model', 'N/A')}")
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                endpoint,
                headers=self._build_headers(),
                json=payload,
            )
            if response.status_code == 429:
                logger.warning("触发限流(429)，等待重试...")
                raise httpx.HTTPStatusError(
                    "Rate limited", request=response.request, response=response
                )
            response.raise_for_status()
            result = response.json()
            logger.info(f"AI响应: status={response.status_code}, tokens={result.get('usage', {})}")
            return result

    async def _stream_request(self, endpoint: str, payload: dict) -> AsyncGenerator[str, None]:
        """流式 SSE 请求 - 逐 token 返回"""
        payload["stream"] = True
        logger.info(f"AI流式请求: {endpoint}, model={payload.get('model', 'N/A')}")

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            async with client.stream(
                "POST",
                endpoint,
                headers=self._build_headers(),
                json=payload,
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line or not line.startswith("data: "):
                        continue
                    data_str = line[6:]  # 去掉 "data: " 前缀
                    if data_str.strip() == "[DONE]":
                        break
                    try:
                        data = json.loads(data_str)
                        delta = data.get("choices", [{}])[0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            yield content
                    except json.JSONDecodeError:
                        continue
