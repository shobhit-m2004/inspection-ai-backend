from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.analysis import AnalysisRead, AnalysisRunRequest, AnalysisRunResponse
from app.services.analysis_service import analysis_service

router = APIRouter()


@router.post('/run', response_model=AnalysisRunResponse)
def run_analysis(payload: AnalysisRunRequest, db: Session = Depends(get_db)):
    analysis = analysis_service.run_analysis(
        db=db,
        sop_document_id=payload.sop_document_id,
        log_document_id=payload.log_document_id,
    )
    findings = analysis.result_json.get('findings', [])
    return AnalysisRunResponse(
        analysis_id=analysis.id,
        sop_document_id=analysis.sop_document_id,
        log_document_id=analysis.log_document_id,
        summary=analysis.summary_json,
        findings=findings,
    )


@router.get('', response_model=list[AnalysisRead])
def list_analyses(db: Session = Depends(get_db)):
    return analysis_service.list_analyses(db)


@router.get('/{analysis_id}', response_model=AnalysisRead)
def get_analysis(analysis_id: int, db: Session = Depends(get_db)):
    return analysis_service.get_analysis(db, analysis_id)
