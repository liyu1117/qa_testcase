"""豆包多模态模型客户端 - 用于UI测试用例生成(图文分析)"""

import logging

from backend.app.core.ai.base_client import DoubaoBaseClient
from backend.app.core.ai.model_registry import get_model_config

logger = logging.getLogger(__name__)


class MultimodalClient(DoubaoBaseClient):
    """多模态模型客户端 - 支持图片+文本输入"""

    async def analyze_with_image(
        self,
        prompt: str,
        image_url: str,
        system_prompt: str = "",
        model_alias: str = "vision-pro",
        max_tokens: int | None = None,
    ) -> str:
        """图文混合输入分析"""
        config = get_model_config(model_alias)
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        # 多模态消息格式：content 为数组
        user_content = [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": image_url}},
        ]
        messages.append({"role": "user", "content": user_content})

        payload = {
            "model": config.model_id,
            "messages": messages,
            "max_tokens": max_tokens or config.max_tokens,
        }

        result = await self._post_request(config.endpoint, payload)
        content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
        return content

    async def analyze_with_images(
        self,
        prompt: str,
        image_urls: list[str],
        system_prompt: str = "",
        model_alias: str = "vision-pro",
        max_tokens: int | None = None,
    ) -> str:
        """多图分析"""
        config = get_model_config(model_alias)
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        user_content = [{"type": "text", "text": prompt}]
        for url in image_urls:
            user_content.append({"type": "image_url", "image_url": {"url": url}})
        messages.append({"role": "user", "content": user_content})

        payload = {
            "model": config.model_id,
            "messages": messages,
            "max_tokens": max_tokens or config.max_tokens,
        }

        result = await self._post_request(config.endpoint, payload)
        content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
        return content
