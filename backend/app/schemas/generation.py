from datetime import datetime

from pydantic import BaseModel


class GenerationJobCreate(BaseModel):
    name: str
    job_type: str  # functional/ui/api
    requirement_id: int
    spec_id: int | None = None
    figma_url: str | None = None
    yapi_project_id: str | None = None
    yapi_token: str | None = None
    yapi_interface_paths: list[str] | None = None
    ai_model: str | None = None


class GenerationJobOut(BaseModel):
    id: int
    name: str
    job_type: str
    requirement_id: int
    spec_id: int | None
    figma_url: str | None
    yapi_project_id: str | None
    yapi_token: str | None = None
    yapi_interface_paths: list[str] | None = None
    ai_model: str | None
    status: str
    progress: int
    result_file_path: str | None
    requirement_content: str | None
    pytest_script_content: str | None = None
    raw_output: str | None = None
    yapi_doc_content: str | None = None
    error_message: str | None
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}
