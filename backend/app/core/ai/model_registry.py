"""豆包模型注册表 - 模型别名到配置的映射"""

from dataclasses import dataclass, field

from backend.config import settings


@dataclass
class ModelConfig:
    model_id: str
    endpoint: str
    max_tokens: int = 4096
    temperature: float = 0.7
    capabilities: list[str] = field(default_factory=list)


# 模型注册表：别名 → 配置
MODEL_REGISTRY: dict[str, ModelConfig] = {}


def init_registry():
    """根据配置初始化模型注册表"""
    base_url = settings.doubao_api_base_url.rstrip("/")
    chat_endpoint = f"{base_url}/chat/completions"

    MODEL_REGISTRY.update({
        "chat-pro": ModelConfig(
            model_id=settings.doubao_chat_model,
            endpoint=chat_endpoint,
            max_tokens=4096,
            temperature=0.7,
            capabilities=["text-generation", "reasoning"],
        ),
        "code-pro": ModelConfig(
            model_id=settings.doubao_code_model,
            endpoint=chat_endpoint,
            max_tokens=4096,
            temperature=0.3,
            capabilities=["code-generation", "text-generation"],
        ),
        "vision-pro": ModelConfig(
            model_id=settings.doubao_vision_model,
            endpoint=chat_endpoint,
            max_tokens=4096,
            temperature=0.7,
            capabilities=["multimodal", "image-understanding"],
        ),
        "embedding": ModelConfig(
            model_id=settings.doubao_embedding_model,
            endpoint=f"{base_url}/embeddings",
            max_tokens=0,
            capabilities=["embedding"],
        ),
    })


def get_model_config(alias: str) -> ModelConfig:
    if not MODEL_REGISTRY:
        init_registry()
    if alias not in MODEL_REGISTRY:
        raise ValueError(f"未知模型别名: {alias}, 可用: {list(MODEL_REGISTRY.keys())}")
    return MODEL_REGISTRY[alias]
