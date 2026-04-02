"""HTTP 请求执行器"""

import logging
import time
from dataclasses import dataclass

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

logger = logging.getLogger(__name__)


@dataclass
class HttpResponse:
    status_code: int
    headers: dict
    body: dict | str | None
    latency_ms: int


class HttpRunner:
    """HTTP 接口自动化执行器"""

    def __init__(self, timeout: float = 30.0, max_retries: int = 3):
        self.timeout = timeout
        self.max_retries = max_retries

    async def execute(
        self,
        method: str,
        url: str,
        headers: dict | None = None,
        body: dict | None = None,
    ) -> tuple[HttpResponse, int]:
        """
        执行 HTTP 请求，返回 (响应, 重试次数)
        """
        last_error = None
        retry_count = 0

        for attempt in range(self.max_retries):
            try:
                start_time = time.monotonic()
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.request(
                        method=method.upper(),
                        url=url,
                        headers=headers,
                        json=body if body and method.upper() in ("POST", "PUT", "PATCH") else None,
                        params=body if body and method.upper() == "GET" else None,
                    )
                latency_ms = int((time.monotonic() - start_time) * 1000)

                # 解析响应体
                try:
                    resp_body = response.json()
                except Exception:
                    resp_body = response.text

                return HttpResponse(
                    status_code=response.status_code,
                    headers=dict(response.headers),
                    body=resp_body,
                    latency_ms=latency_ms,
                ), retry_count

            except (httpx.TimeoutException, httpx.ConnectError) as e:
                last_error = e
                retry_count = attempt + 1
                if attempt < self.max_retries - 1:
                    wait_time = (attempt + 1) * 1.0
                    logger.warning(f"请求失败({type(e).__name__}), {wait_time}s 后重试 ({retry_count}/{self.max_retries})")
                    import asyncio
                    await asyncio.sleep(wait_time)

        raise last_error or Exception("请求执行失败")
