from datetime import datetime

from sqlalchemy import String, Text, Integer, DateTime, ForeignKey, JSON, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database import Base


class Testcase(Base):
    __tablename__ = "testcases"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    case_type: Mapped[str] = mapped_column(String(20), nullable=False)  # functional/ui/api
    priority: Mapped[str] = mapped_column(String(5), default="P2")  # P0/P1/P2/P3
    module: Mapped[str | None] = mapped_column(String(100))
    precondition: Mapped[str | None] = mapped_column(Text)
    steps: Mapped[dict | None] = mapped_column(JSON)
    expected_result: Mapped[str | None] = mapped_column(Text)
    content_md: Mapped[str | None] = mapped_column(Text)
    generation_job_id: Mapped[int | None] = mapped_column(ForeignKey("generation_jobs.id"))
    requirement_id: Mapped[int | None] = mapped_column(ForeignKey("requirements.id"))
    status: Mapped[str] = mapped_column(String(20), default="draft")  # draft/reviewed/approved

    # 接口测试用例专用字段
    api_method: Mapped[str | None] = mapped_column(String(10))
    api_path: Mapped[str | None] = mapped_column(String(500))
    api_headers: Mapped[dict | None] = mapped_column(JSON)
    api_request_body: Mapped[dict | None] = mapped_column(JSON)
    api_assertions: Mapped[list | None] = mapped_column(JSON)

    tags: Mapped[list | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    # relationships
    generation_job = relationship("GenerationJob", back_populates="testcases")
    requirement = relationship("Requirement", back_populates="testcases")
    execution_results = relationship("ExecutionResult", back_populates="testcase")
