from datetime import datetime

from sqlalchemy import String, Text, Integer, DateTime, ForeignKey, JSON, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database import Base


class GenerationJob(Base):
    __tablename__ = "generation_jobs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    job_type: Mapped[str] = mapped_column(String(20), nullable=False)  # functional/ui/api
    requirement_id: Mapped[int] = mapped_column(ForeignKey("requirements.id"), nullable=False)
    spec_id: Mapped[int | None] = mapped_column(ForeignKey("testcase_specs.id"))
    figma_url: Mapped[str | None] = mapped_column(String(500))
    yapi_project_id: Mapped[str | None] = mapped_column(String(100))
    yapi_token: Mapped[str | None] = mapped_column(String(200))  # 每个项目独立的 YApi Token
    yapi_interface_paths: Mapped[list | None] = mapped_column(JSON)  # ["/api/v1/xxx", ...]
    ai_model: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending/running/success/failed
    progress: Mapped[int] = mapped_column(Integer, default=0)
    result_file_path: Mapped[str | None] = mapped_column(String(500))
    prompt_snapshot: Mapped[str | None] = mapped_column(Text)
    raw_output: Mapped[str | None] = mapped_column(Text)
    requirement_content: Mapped[str | None] = mapped_column(Text)  # 本次读取到的需求内容快照
    pytest_script_content: Mapped[str | None] = mapped_column(Text)       # AI 生成的 pytest 脚本
    pytest_script_path: Mapped[str | None] = mapped_column(String(500))  # 脚本文件路径
    structured_json: Mapped[dict | None] = mapped_column(JSON)           # A方案预留: 结构化中间结果
    yapi_doc_content: Mapped[str | None] = mapped_column(Text)  # YApi 接口文档快照
    error_message: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    # relationships
    requirement = relationship("Requirement", back_populates="generation_jobs")
    spec = relationship("TestcaseSpec")
    testcases = relationship("Testcase", back_populates="generation_job")
