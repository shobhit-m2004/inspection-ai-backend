from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import DocumentStatus, DocumentType


class DocumentUploadResponse(BaseModel):
    id: int
    type: DocumentType
    original_filename: str
    status: DocumentStatus
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DocumentSummary(BaseModel):
    id: int
    type: DocumentType
    original_filename: str
    status: DocumentStatus
    created_at: datetime
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class DocumentDetail(BaseModel):
    id: int
    type: DocumentType
    original_filename: str
    storage_path: str
    raw_text: str
    extracted_json: dict[str, Any] | None = None
    approved_json: dict[str, Any] | None = None
    status: DocumentStatus
    created_at: datetime
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class ExtractRequest(BaseModel):
    mode: Literal['auto', 'manual'] = 'auto'
    selected_parameters: list[str] = Field(default_factory=list)


class ExtractResponse(BaseModel):
    document_id: int
    review_session_id: int
    extracted_json: dict[str, Any]
    warnings: list[str] = Field(default_factory=list)


class ApproveRequest(BaseModel):
    approved_json: dict[str, Any] | None = None


class ApproveResponse(BaseModel):
    document_id: int
    status: DocumentStatus
    approved_json: dict[str, Any]
