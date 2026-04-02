from datetime import datetime

from pydantic import BaseModel


class ExecutionJobCreate(BaseModel):
    name: str
    generation_job_id: int  # 关联的生成任务ID，执行该任务下所有用例
    env_config: dict  # {base_url, headers, timeout...}
    execution_mode: str = "pytest"  # httpx / pytest


class ExecutionJobOut(BaseModel):
    id: int
    name: str
    generation_job_id: int | None
    execution_mode: str
    env_config: dict | None
    status: str
    total_cases: int
    passed: int
    failed: int
    skipped: int
    duration: float | None
    report_path: str | None
    pytest_script_path: str | None = None
    error_message: str | None
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ExecutionResultOut(BaseModel):
    id: int
    execution_job_id: int
    testcase_id: int
    testcase_title: str | None = None
    status: str
    request_info: dict | None
    response_info: dict | None
    assertion_results: list[dict] | None
    retry_count: int
    pytest_nodeid: str | None = None
    pytest_error_detail: str | None = None
    error_message: str | None
    executed_at: datetime | None

    model_config = {"from_attributes": True}
