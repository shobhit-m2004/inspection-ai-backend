from fastapi import APIRouter, Depends, status, Response
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.orm import Session
from typing import Any, Optional
from datetime import datetime
import uuid
import json
import io
import os

from app.db.session import get_db
from app.models import SOP, Log, ComplianceResult, SOPChunk, LogChunk, User
from app.schemas import ReportRequest, ReportResponse
from app.utils.security import get_current_user_optional
from app.core.exceptions import BadRequestException
from app.core.logging_config import get_logger
from app.services.faiss_store import search
from app.services.report_llm import generate_report
from app.services.pdf_report import build_pdf_report

router = APIRouter(prefix="/reports", tags=["Reports"])
logger = get_logger(__name__)


@router.post(
    "/generate",
    response_model=ReportResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate compliance report",
    description="Generate a detailed compliance report with parameter-level comparison",
    responses={
        400: {"description": "Invalid request parameters"},
    },
)
def generate_report_endpoint(
    payload: ReportRequest,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_optional),
) -> Any:
    """
    Generate a compliance report with detailed parameter comparison.

    - **sop_id**: Optional SOP ID to filter report
    - **log_id**: Optional log ID to filter report
    - **include_details**: Include detailed analysis in report
    """
    # Validate SOP if provided
    if payload.sop_id:
        sop = db.query(SOP).filter(SOP.id == payload.sop_id).first()
        if not sop:
            raise BadRequestException(detail=f"SOP with ID {payload.sop_id} not found")

    # Validate log if provided
    if payload.log_id:
        log = db.query(Log).filter(Log.id == payload.log_id).first()
        if not log:
            raise BadRequestException(detail=f"Log with ID {payload.log_id} not found")

    sop_id = payload.sop_id
    log_id = payload.log_id

    # If no IDs provided, try to use the latest compliance result
    if not sop_id or not log_id:
        latest = (
            db.query(ComplianceResult)
            .order_by(ComplianceResult.analyzed_at.desc())
            .first()
        )
        if latest and not sop_id:
            sop_id = latest.sop_id
        if latest and not log_id:
            log_id = latest.log_id

    if not sop_id or not log_id:
        raise BadRequestException(detail="Provide sop_id/log_id or run analysis first.")

    sop = db.query(SOP).filter(SOP.id == sop_id).first()
    log = db.query(Log).filter(Log.id == log_id).first()
    if not sop or not log:
        raise BadRequestException(detail="SOP or Log not found for report generation.")

    sop_chunks = (
        db.query(SOPChunk)
        .filter(SOPChunk.sop_id == sop_id)
        .order_by(SOPChunk.chunk_index)
        .all()
    )

    if not sop_chunks:
        raise BadRequestException(detail="SOP rules not found. Re-upload SOP to extract rules.")

    # Build rule matches using embedding search
    rule_matches = []
    for chunk in sop_chunks:
        if not chunk.embedding_vector:
            continue
        matches = search("log_chunk", chunk.embedding_vector, top_k=3)
        best_match = None
        best_score = None
        for match_id, score in matches:
            log_chunk = db.query(LogChunk).filter(LogChunk.id == match_id).first()
            if log_chunk and log_chunk.log_id == log_id:
                best_match = log_chunk
                best_score = score
                break
        if best_match:
            rule_matches.append({
                "rule": chunk.content,
                "log_excerpt": best_match.content,
                "score": round(float(best_score), 4),
            })

    report_data = generate_report(sop.title, log.title, rule_matches)

    # Generate report ID
    report_id = str(uuid.uuid4())

    logger.info(
        "Report generated",
        report_id=report_id,
        user_id=getattr(current_user, "id", None),
        sop_id=sop_id,
        log_id=log_id,
        result_count=len(rule_matches),
    )

    return {
        "report_id": report_id,
        "status": "completed",
        "download_url": f"/reports/download/{report_id}",
        "generated_at": datetime.utcnow(),
        "report": report_data,
    }


@router.get(
    "/download/{report_id}",
    summary="Download report",
    description="Download a generated compliance report in JSON or PDF format",
    responses={
        404: {"description": "Report not found"},
    },
)
def download_report(
    report_id: str,
    format: str = "pdf",
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_optional),
) -> Any:
    """
    Download a generated report in JSON or PDF format.
    
    For JSON format: Returns the full report data as a JSON file.
    For PDF format: Returns a formatted text representation (PDF generation requires additional library).
    """
    # In a real implementation, this would retrieve the report from storage
    # For now, we'll generate a fresh report for demonstration
    
    # Get the latest compliance result to generate report
    latest = (
        db.query(ComplianceResult)
        .order_by(ComplianceResult.analyzed_at.desc())
        .first()
    )
    
    if not latest:
        raise BadRequestException(detail="No analysis results found. Run analysis first.")
    
    sop = db.query(SOP).filter(SOP.id == latest.sop_id).first()
    log = db.query(Log).filter(Log.id == latest.log_id).first()
    
    if not sop or not log:
        raise BadRequestException(detail="SOP or Log not found.")
    
    sop_chunks = (
        db.query(SOPChunk)
        .filter(SOPChunk.sop_id == latest.sop_id)
        .order_by(SOPChunk.chunk_index)
        .all()
    )
    
    if not sop_chunks:
        raise BadRequestException(detail="SOP rules not found.")
    
    # Build rule matches
    rule_matches = []
    for chunk in sop_chunks:
        if not chunk.embedding_vector:
            continue
        matches = search("log_chunk", chunk.embedding_vector, top_k=3)
        best_match = None
        best_score = None
        for match_id, score in matches:
            log_chunk = db.query(LogChunk).filter(LogChunk.id == match_id).first()
            if log_chunk and log_chunk.log_id == latest.log_id:
                best_match = log_chunk
                best_score = score
                break
        if best_match:
            rule_matches.append({
                "rule": chunk.content,
                "log_excerpt": best_match.content,
                "score": round(float(best_score), 4),
            })
    
    report_data = generate_report(sop.title, log.title, rule_matches)
    
    # Add metadata
    report_data["report_id"] = report_id
    report_data["sop_title"] = sop.title
    report_data["log_title"] = log.title
    report_data["sop_id"] = latest.sop_id
    report_data["log_id"] = latest.log_id
    
    if format.lower() == "json":
        # Return as JSON file download
        json_str = json.dumps(report_data, indent=2, ensure_ascii=False)
        return Response(
            content=json_str,
            media_type="application/json",
            headers={
                "Content-Disposition": f'attachment; filename="compliance_report_{report_id}.json"'
            },
        )
    elif format.lower() == "pdf":
        pdf_dir = "app/data/reports"
        pdf_path = f"{pdf_dir}/{report_id}.pdf"
        build_pdf_report(pdf_path, report_data)
        return FileResponse(
            pdf_path,
            media_type="application/pdf",
            filename=f"compliance_report_{report_id}.pdf",
        )
    elif format.lower() == "txt":
        report_text = generate_text_report(report_data)
        return Response(
            content=report_text,
            media_type="text/plain",
            headers={
                "Content-Disposition": f'attachment; filename="compliance_report_{report_id}.txt"'
            },
        )
    else:
        raise BadRequestException(detail="Invalid format. Use 'json' or 'pdf' or 'txt'.")


def generate_text_report(report_data: dict) -> str:
    """Generate a human-readable text report from report data."""
    lines = []
    lines.append("=" * 80)
    lines.append("PHARMA SOP COMPLIANCE AUDIT REPORT")
    lines.append("=" * 80)
    lines.append("")
    lines.append(f"Report ID: {report_data.get('report_id', 'N/A')}")
    lines.append(f"SOP: {report_data.get('sop_title', 'N/A')} (ID: {report_data.get('sop_id', 'N/A')})")
    lines.append(f"Log: {report_data.get('log_title', 'N/A')} (ID: {report_data.get('log_id', 'N/A')})")
    lines.append(f"Generated: {report_data.get('generated_at', datetime.utcnow().isoformat())}")
    lines.append("")
    lines.append("-" * 80)
    lines.append("EXECUTIVE SUMMARY")
    lines.append("-" * 80)
    lines.append(f"Overall Compliance Score: {report_data.get('overall_score', 0)*100:.1f}%")
    lines.append(f"Severity Level: {report_data.get('severity', 'N/A')}")
    lines.append(f"Severity Confidence: {report_data.get('severity_confidence', 0)*100:.1f}%")
    lines.append(f"Total Parameters Checked: {report_data.get('total_parameters', 0)}")
    lines.append(f"Compliant Parameters: {report_data.get('compliant_parameters', 0)}")
    lines.append(f"Parameters with Deviations: {report_data.get('deviation_parameters', 0)}")
    lines.append(f"Missing Parameters: {len(report_data.get('missing_parameters', []))}")
    lines.append("")
    lines.append(f"Summary: {report_data.get('summary', 'N/A')}")
    lines.append("")
    
    # Missing Parameters Section
    missing_params = report_data.get("missing_parameters", [])
    if missing_params:
        lines.append("-" * 80)
        lines.append("MISSING PARAMETERS (Not found in logs)")
        lines.append("-" * 80)
        for i, param in enumerate(missing_params, 1):
            lines.append(f"{i}. Parameter: {param.get('parameter', 'Unknown')}")
            lines.append(f"   Expected: {param.get('expected', 'N/A')}")
            lines.append(f"   Reason: {param.get('reason', 'N/A')}")
            lines.append("")
    
    # Parameter Comparison Table
    param_comparison = report_data.get("parameter_comparison", [])
    if param_comparison:
        lines.append("-" * 80)
        lines.append("DETAILED PARAMETER COMPARISON")
        lines.append("-" * 80)
        lines.append(f"{'Parameter':<30} {'Expected':<20} {'Actual':<20} {'Status':<12} {'Score':<8}")
        lines.append("-" * 90)
        for item in param_comparison:
            param = (item.get('parameter', 'Unknown')[:28] + '..') if len(item.get('parameter', '')) > 30 else item.get('parameter', 'Unknown')
            expected = (item.get('expected', 'N/A')[:18] + '..') if len(item.get('expected', '')) > 20 else item.get('expected', 'N/A')
            actual = (item.get('actual', 'N/A')[:18] + '..') if len(item.get('actual', '')) > 20 else item.get('actual', 'N/A')
            status = item.get('status', 'unknown')
            score = f"{item.get('score', 0)*100:.0f}%"
            lines.append(f"{param:<30} {expected:<20} {actual:<20} {status:<12} {score:<8}")
        lines.append("")
    
    # Gaps Section
    gaps = report_data.get("gaps", [])
    if gaps:
        lines.append("-" * 80)
        lines.append("COMPLIANCE GAPS")
        lines.append("-" * 80)
        for i, gap in enumerate(gaps, 1):
            lines.append(f"{i}. Severity: {gap.get('severity', 'N/A')}")
            lines.append(f"   Expected (SOP): {gap.get('expected', 'N/A')[:200]}")
            lines.append(f"   Observed (Log): {gap.get('observed', 'N/A')[:200]}")
            lines.append(f"   Recommendation: {gap.get('recommendation', 'N/A')}")
            lines.append("")
    
    lines.append("=" * 80)
    lines.append("END OF REPORT")
    lines.append("=" * 80)
    
    return "\n".join(lines)

