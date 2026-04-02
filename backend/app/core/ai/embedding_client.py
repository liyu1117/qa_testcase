"""豆包向量化模型客户端 - 预留用于用例去重/相似性检索"""

import logging

from backend.app.core.ai.base_client import DoubaoBaseClient
from backend.app.core.ai.model_registry import get_model_config

logger = logging.getLogger(__name__)


class EmbeddingClient(DoubaoBaseClient):
    """向量化模型客户端"""

    async def embed_text(self, text: str, model_alias: str = "embedding") -> list[float]:
        """单文本向量化"""
        config = get_model_config(model_alias)
        payload = {
            "model": config.model_id,
            "input": text,
        }
        result = await self._post_request(config.endpoint, payload)
        return result.get("data", [{}])[0].get("embedding", [])

    async def embed_batch(self, texts: list[str], model_alias: str = "embedding") -> list[list[float]]:
        """批量文本向量化"""
        config = get_model_config(model_alias)
        payload = {
            "model": config.model_id,
            "input": texts,
        }
        result = await self._post_request(config.endpoint, payload)
        return [item.get("embedding", []) for item in result.get("data", [])]
