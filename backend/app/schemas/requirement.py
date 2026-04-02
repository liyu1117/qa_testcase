from datetime import datetime

from pydantic import BaseModel


class RequirementCreate(BaseModel):
    title: str
    description: str | None = None
    source_type: str | None = None
    source_id: str | None = None
    source_url: str | None = None
    raw_content: str | None = None
    assignee: str | None = None


class RequirementUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    source_type: str | None = None
    source_id: str | None = None
    source_url: str | None = None
    raw_content: str | None = None
    status: str | None = None
    assignee: str | None = None


class RequirementOut(BaseModel):
    id: int
    title: str
    description: str | None
    source_type: str | None
    source_id: str | None
    source_url: str | None
    raw_content: str | None
    status: str
    assignee: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
