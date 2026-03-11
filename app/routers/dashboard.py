from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Any, List

from app.db.session import get_db
from app.models import SOP, Log, ComplianceResult, User
from app.schemas import DashboardResponse, ComplianceResult as ComplianceResultSchema
from app.utils.security import get_current_user_optional
from app.core.logging_config import get_logger

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])
logger = get_logger(__name__)


@router.get(
    "",
    response_model=DashboardResponse,
    summary="Get dashboard metrics",
    description="Get compliance dashboard with key metrics and recent analyses",
)
def get_dashboard(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_optional),
) -> Any:
    """
    Get dashboard with compliance metrics and statistics.
    
    Returns:
    - Total SOPs and logs count
    - Total analyses performed
    - Average compliance score
    - Compliance breakdown by severity
    - Recent analysis results
    """
    # Get counts
    total_sops = db.query(SOP).count()
    total_logs = db.query(Log).count()
    total_analyses = db.query(ComplianceResult).count()
    
    # Get average compliance score
    avg_score_result = db.query(func.avg(ComplianceResult.similarity_score)).scalar()
    average_compliance_score = round(float(avg_score_result) if avg_score_result else 0.0, 2)
    
    # Get compliance by severity
    severity_counts = {
        "Low": db.query(ComplianceResult).filter(
            ComplianceResult.gap_summary.contains("Low")
        ).count(),
        "Medium": db.query(ComplianceResult).filter(
            ComplianceResult.gap_summary.contains("Medium")
        ).count(),
        "High": db.query(ComplianceResult).filter(
            ComplianceResult.gap_summary.contains("High")
        ).count(),
    }
    
    # Get recent analyses
    recent = (
        db.query(ComplianceResult)
        .order_by(ComplianceResult.analyzed_at.desc())
        .limit(5)
        .all()
    )
    
    recent_analyses = []
    for result in recent:
        # Extract severity from gap_summary
        severity = "Medium"
        if "Low" in result.gap_summary:
            severity = "Low"
        elif "High" in result.gap_summary:
            severity = "High"
        
        recent_analyses.append({
            "id": result.id,
            "sop_id": result.sop_id,
            "log_id": result.log_id,
            "similarity_score": round(result.similarity_score, 4),
            "gap_summary": result.gap_summary.replace(f"(Severity: {severity})", "").strip(),
            "matched_chunks": 0,  # These would need to be stored in the model
            "total_chunks": 0,
            "coverage": round(result.similarity_score, 4),  # Approximation
            "temporal_consistency": 1.0,  # Not stored, would need model update
            "severity": severity,
            "severity_confidence": 0.8,  # Not stored, would need model update
            "analyzed_at": result.analyzed_at,
        })
    
    logger.info(
        "Dashboard accessed",
        user_id=getattr(current_user, "id", None),
        total_sops=total_sops,
        total_logs=total_logs,
    )
    
    return {
        "total_sops": total_sops,
        "total_logs": total_logs,
        "total_analyses": total_analyses,
        "average_compliance_score": average_compliance_score,
        "compliance_by_severity": severity_counts,
        "recent_analyses": recent_analyses,
    }


@router.get(
    "/summary",
    summary="Get compliance summary",
    description="Get a brief summary of compliance status",
)
def get_compliance_summary(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_optional),
) -> Any:
    """
    Get a brief compliance summary.
    """
    total_sops = db.query(SOP).count()
    total_logs = db.query(Log).count()
    total_analyses = db.query(ComplianceResult).count()
    
    avg_score_result = db.query(func.avg(ComplianceResult.similarity_score)).scalar()
    avg_score = round(float(avg_score_result) if avg_score_result else 0.0, 2)
    
    # Determine overall status
    if avg_score >= 0.8:
        status = "compliant"
    elif avg_score >= 0.5:
        status = "partial_compliance"
    else:
        status = "non_compliant"
    
    return {
        "status": status,
        "total_sops": total_sops,
        "total_logs": total_logs,
        "total_analyses": total_analyses,
        "average_compliance_score": avg_score,
    }

