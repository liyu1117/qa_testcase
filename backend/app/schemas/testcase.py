from datetime import datetime

from pydantic import BaseModel


class TestcaseSpecCreate(BaseModel):
    name: str
    spec_type: str  # functional/ui/api
    content: str
    is_default: bool = False


class TestcaseSpecUpdate(BaseModel):
    name: str | None = None
    spec_type: str | None = None
    content: str | None = None
    is_default: bool | None = None


class TestcaseSpecOut(BaseModel):
    id: int
    name: str
    spec_type: str
    content: str
    is_default: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TestcaseCreate(BaseModel):
    title: str
    case_type: str  # functional/ui/api
    priority: str = "P2"
    module: str | None = None
    precondition: str | None = None
    steps: list[dict] | None = None
    expected_result: str | None = None
    content_md: str | None = None
    requirement_id: int | None = None
    api_method: str | None = None
    api_path: str | None = None
    api_headers: dict | None = None
    api_request_body: dict | None = None
    api_assertions: list[dict] | None = None
    tags: list[str] | None = None


class TestcaseUpdate(BaseModel):
    title: str | None = None
    priority: str | None = None
    module: str | None = None
    precondition: str | None = None
    steps: list[dict] | None = None
    expected_result: str | None = None
    content_md: str | None = None
    status: str | None = None
    api_method: str | None = None
    api_path: str | None = None
    api_headers: dict | None = None
    api_request_body: dict | None = None
    api_assertions: list[dict] | None = None
    tags: list[str] | None = None


class TestcaseOut(BaseModel):
    id: int
    title: str
    case_type: str
    priority: str
    module: str | None
    precondition: str | None
    steps: list[dict] | None
    expected_result: str | None
    content_md: str | None
    generation_job_id: int | None
    requirement_id: int | None
    status: str
    api_method: str | None
    api_path: str | None
    api_headers: dict | None
    api_request_body: dict | None
    api_assertions: list[dict] | None
    tags: list[str] | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
