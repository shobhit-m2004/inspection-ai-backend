from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AssistantRequest(BaseModel):
    review_session_id: int | None = None
    message: str
    current_json: dict[str, Any] | None = None


class AssistantResponse(BaseModel):
    review_session_id: int
    message: str
    updated_json: dict[str, Any] | None = None
    changed: bool = False


class AssistantMessageRead(BaseModel):
    id: int
    role: str
    message: str
    updated_json_snapshot: dict[str, Any] | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ReviewSessionRead(BaseModel):
    id: int
    document_id: int
    selected_parameters: dict[str, Any] | None = None
    session_status: str
    created_at: datetime
    updated_at: datetime | None = None
    messages: list[AssistantMessageRead] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)

