from datetime import datetime

from sqlalchemy import String, Integer, Text, DateTime, ForeignKey, JSON, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database import Base


class ExecutionResult(Base):
    __tablename__ = "execution_results"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    execution_job_id: Mapped[int] = mapped_column(ForeignKey("execution_jobs.id"), nullable=False)
    testcase_id: Mapped[int] = mapped_column(ForeignKey("testcases.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pass/fail/error/skip
    request_info: Mapped[dict | None] = mapped_column(JSON)
    response_info: Mapped[dict | None] = mapped_column(JSON)  # {status_code, headers, body, latency_ms}
    assertion_results: Mapped[list | None] = mapped_column(JSON)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    pytest_nodeid: Mapped[str | None] = mapped_column(String(300))   # pytest test nodeid
    pytest_error_detail: Mapped[str | None] = mapped_column(Text)    # pytest 详细错误栈
    error_message: Mapped[str | None] = mapped_column(Text)
    executed_at: Mapped[datetime | None] = mapped_column(DateTime)

    # relationships
    execution_job = relationship("ExecutionJob", back_populates="results")
    testcase = relationship("Testcase", back_populates="execution_results")
