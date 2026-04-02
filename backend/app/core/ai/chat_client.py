"""豆包文本模型客户端 - 用于功能/接口测试用例生成"""

import logging
from typing import AsyncGenerator

from backend.app.core.ai.base_client import DoubaoBaseClient
from backend.app.core.ai.model_registry import get_model_config

logger = logging.getLogger(__name__)


class ChatClient(DoubaoBaseClient):
    """文本对话模型客户端"""

    async def generate(
        self,
        prompt: str,
        system_prompt: str = "",
        model_alias: str = "chat-pro",
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> str:
        """同步生成（等待完整响应）"""
        config = get_model_config(model_alias)
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": config.model_id,
            "messages": messages,
            "max_tokens": max_tokens or config.max_tokens,
            "temperature": temperature if temperature is not None else config.temperature,
        }

        result = await self._post_request(config.endpoint, payload)
        content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
        return content

    async def stream_generate(
        self,
        prompt: str,
        system_prompt: str = "",
        model_alias: str = "chat-pro",
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> AsyncGenerator[str, None]:
        """流式生成 - 逐 token 返回"""
        config = get_model_config(model_alias)
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": config.model_id,
            "messages": messages,
            "max_tokens": max_tokens or config.max_tokens,
            "temperature": temperature if temperature is not None else config.temperature,
        }

        async for token in self._stream_request(config.endpoint, payload):
            yield token
