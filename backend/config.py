import json
from pathlib import Path
from pydantic_settings import BaseSettings
from pydantic import field_validator


class Settings(BaseSettings):
    # 数据库
    database_url: str = "sqlite+aiosqlite:///./backend/data/qa_master.db"

    # 豆包 AI 模型
    doubao_api_key: str = ""
    doubao_api_base_url: str = "https://maas-api.ml-platform-cn-beijing.volces.com/api/v3"
    doubao_chat_model: str = "doubao-pro-32k"
    doubao_code_model: str = "doubao-pro-32k"
    doubao_vision_model: str = "doubao-vision-pro-32k"
    doubao_embedding_model: str = "doubao-embedding"

    # 钉钉
    dingtalk_app_key: str = ""
    dingtalk_app_secret: str = ""
    dingtalk_webhook_url: str = ""
    dingtalk_webhook_secret: str = ""
    dingtalk_mcp_url: str = ""
    dingtalk_folder_id: str = ""
    dingtalk_workspace_id: str = ""

    # Figma
    figma_access_token: str = ""

    # YApi
    yapi_base_url: str = "https://yapi.xhey.top"
    yapi_token: str = ""

    # 服务配置
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    app_debug: bool = True
    cors_origins: list[str] = ["*"]

    # 路径
    base_dir: Path = Path(__file__).parent
    data_dir: Path = Path(__file__).parent / "data"
    exports_dir: Path = Path(__file__).parent / "data" / "exports"
    reports_dir: Path = Path(__file__).parent / "data" / "reports"
    pytest_scripts_dir: Path = Path(__file__).parent / "data" / "pytest_scripts"
    prompts_dir: Path = Path(__file__).parent / "prompts"

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            return json.loads(v)
        return v

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
