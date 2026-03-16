from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class AnalysisRunRequest(BaseModel):
    sop_document_id: int
    log_document_id: int


class AnalysisFinding(BaseModel):
    rule_id: str
    parameter: str
    status: str
    matched_observations: list[str]
    explanation: str
    severity: str


class AnalysisRunResponse(BaseModel):
    analysis_id: int
    sop_document_id: int
    log_document_id: int
    summary: dict[str, Any]
    findings: list[AnalysisFinding]


class AnalysisRead(BaseModel):
    id: int
    sop_document_id: int
    log_document_id: int
    result_json: dict[str, Any]
    summary_json: dict[str, Any]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
