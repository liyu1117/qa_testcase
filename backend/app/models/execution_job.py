from datetime import datetime

from sqlalchemy import String, Integer, Float, Text, DateTime, ForeignKey, JSON, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database import Base


class ExecutionJob(Base):
    __tablename__ = "execution_jobs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    generation_job_id: Mapped[int | None] = mapped_column(ForeignKey("generation_jobs.id"))  # 关联的生成任务
    execution_mode: Mapped[str] = mapped_column(String(20), default="pytest")  # httpx / pytest
    env_config: Mapped[dict | None] = mapped_column(JSON)  # {base_url, headers, timeout...}
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending/running/success/failed/partial_fail
    total_cases: Mapped[int] = mapped_column(Integer, default=0)
    passed: Mapped[int] = mapped_column(Integer, default=0)
    failed: Mapped[int] = mapped_column(Integer, default=0)
    skipped: Mapped[int] = mapped_column(Integer, default=0)
    duration: Mapped[float | None] = mapped_column(Float)
    report_path: Mapped[str | None] = mapped_column(String(500))
    pytest_script_path: Mapped[str | None] = mapped_column(String(500))  # 本次执行使用的脚本路径
    error_message: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    # relationships
    generation_job = relationship("GenerationJob")
    results = relationship("ExecutionResult", back_populates="execution_job")
