from datetime import datetime
from typing import Optional, List, Any
from pydantic import BaseModel, EmailStr, Field, ConfigDict


# ============== Token Schemas ==============

class Token(BaseModel):
    """Authentication token response."""
    access_token: str
    token_type: str = "bearer"


class TokenPayload(BaseModel):
    """JWT token payload."""
    sub: str
    exp: datetime
    iat: datetime
    type: str


# ============== User Schemas ==============

class UserBase(BaseModel):
    """Base user schema."""
    name: str = Field(..., min_length=1, max_length=120, description="User's full name")
    email: EmailStr = Field(..., description="User's email address")


class UserCreate(UserBase):
    """User creation schema."""
    password: str = Field(..., min_length=8, max_length=100, description="User's password")


class UserUpdate(BaseModel):
    """User update schema."""
    name: Optional[str] = Field(None, min_length=1, max_length=120)
    email: Optional[EmailStr] = None


class UserResponse(UserBase):
    """User response schema."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: Optional[datetime] = None

    model_config = {
        "json_schema_extra": {
            "example": {
                "id": 1,
                "name": "John Doe",
                "email": "john@example.com",
                "created_at": "2024-01-01T00:00:00Z",
            }
        }
    }


class UserInDB(UserBase):
    """User schema for database operations."""
    id: int
    password_hash: str
    created_at: datetime


# ============== Authentication Schemas ==============

class LoginRequest(BaseModel):
    """Login request schema."""
    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    """Login response schema."""
    token: str
    token_type: str = "bearer"
    user: UserResponse


class RegisterRequest(UserCreate):
    """Registration request schema."""
    pass


class RegisterResponse(LoginResponse):
    """Registration response schema."""
    pass


# ============== SOP Schemas ==============

class SOPBase(BaseModel):
    """Base SOP schema."""
    title: str = Field(..., min_length=1, max_length=255, description="SOP document title")


class SOPUploadResponse(SOPBase):
    """SOP upload response schema."""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    uploaded_at: datetime
    chunks: int = Field(..., description="Number of chunks created from SOP")


class SOPListResponse(BaseModel):
    """SOP list response schema."""
    id: int
    title: str
    uploaded_at: datetime
    chunk_count: int


# ============== Log Schemas ==============

class LogBase(BaseModel):
    """Base Log schema."""
    title: str = Field(..., min_length=1, max_length=255, description="Log document title")


class LogUploadResponse(LogBase):
    """Log upload response schema."""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    uploaded_at: datetime
    chunks: int = Field(..., description="Number of chunks created from Log")


class LogListResponse(BaseModel):
    """Log list response schema."""
    id: int
    title: str
    uploaded_at: datetime
    chunk_count: int


# ============== Analysis Schemas ==============

class ComplianceResult(BaseModel):
    """Compliance analysis result schema."""
    id: int
    sop_id: int
    log_id: int
    similarity_score: float = Field(..., ge=0, le=1, description="Similarity score between SOP and Log")
    gap_summary: str = Field(..., description="Summary of identified gaps")
    matched_chunks: int = Field(..., description="Number of matched chunks")
    total_chunks: int = Field(..., description="Total number of SOP chunks")
    coverage: float = Field(..., ge=0, le=1, description="Coverage ratio")
    temporal_consistency: float = Field(..., ge=0, le=1, description="Temporal consistency score")
    severity: str = Field(..., description="Severity level: Low, Medium, High")
    severity_confidence: float = Field(..., ge=0, le=1, description="Severity prediction confidence")
    analyzed_at: datetime


class AnalyzeRequest(BaseModel):
    """Analysis request schema."""
    sop_id: Optional[int] = None
    log_id: Optional[int] = None


class AnalyzeResponse(BaseModel):
    """Analysis response schema."""
    results: List[ComplianceResult]
    total_sops: int = Field(..., description="Total number of SOPs analyzed")
    total_logs: int = Field(..., description="Total number of Logs analyzed")


# ============== Dashboard Schemas ==============

class DashboardMetric(BaseModel):
    """Dashboard metric schema."""
    label: str
    value: Any
    trend: Optional[str] = None


class DashboardResponse(BaseModel):
    """Dashboard response schema."""
    total_sops: int
    total_logs: int
    total_analyses: int
    average_compliance_score: float
    compliance_by_severity: dict[str, int]
    recent_analyses: List[ComplianceResult]


# ============== Report Schemas ==============

class ReportRequest(BaseModel):
    """Report generation request schema."""
    sop_id: Optional[int] = None
    log_id: Optional[int] = None
    include_details: bool = True


class ParameterComparison(BaseModel):
    """Parameter-level comparison schema."""
    parameter: str
    expected: str
    actual: str
    score: float
    status: str  # compliant, deviation, missing
    rule_text: Optional[str] = None
    log_text: Optional[str] = None


class MissingParameter(BaseModel):
    """Missing parameter schema."""
    parameter: str
    expected: str
    reason: str


class ComplianceGap(BaseModel):
    """Compliance gap schema with score."""
    expected: str
    observed: str
    severity: str
    recommendation: str
    score: Optional[float] = None


class ReportData(BaseModel):
    """Detailed report data schema."""
    overall_score: float
    severity: str
    severity_confidence: float
    summary: str
    gaps: Optional[List[ComplianceGap]] = []
    comparison_data: Optional[List[dict]] = []
    parameter_comparison: Optional[List[ParameterComparison]] = []
    missing_parameters: Optional[List[MissingParameter]] = []
    chart: Optional[dict] = None
    generated_at: Optional[str] = None
    total_parameters: Optional[int] = 0
    compliant_parameters: Optional[int] = 0
    deviation_parameters: Optional[int] = 0


class ReportResponse(BaseModel):
    """Report generation response schema."""
    report_id: str
    status: str
    download_url: Optional[str] = None
    generated_at: datetime
    report: Optional[ReportData] = None


# ============== Health Schemas ==============

class HealthStatus(BaseModel):
    """Health check status schema."""
    status: str
    timestamp: datetime
    version: str
    environment: str


class HealthCheck(BaseModel):
    """Health check response schema."""
    status: str
    checks: dict[str, bool]
    timestamp: datetime


# ============== Error Schemas ==============

class ErrorResponse(BaseModel):
    """Error response schema."""
    error: dict[str, Any]


class ValidationErrorDetail(BaseModel):
    """Validation error detail schema."""
    loc: List[str]
    msg: str
    type: str
