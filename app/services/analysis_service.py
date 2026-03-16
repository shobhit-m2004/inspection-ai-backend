from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.analysis import Analysis
from app.models.document import Document
from app.models.enums import DocumentStatus, DocumentType
from app.services.comparison_service import comparison_service


class AnalysisService:
    def run_analysis(self, db: Session, sop_document_id: int, log_document_id: int) -> Analysis:
        sop = db.get(Document, sop_document_id)
        log = db.get(Document, log_document_id)

        if not sop or not log:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='SOP or Log document not found.')
        if sop.type != DocumentType.SOP or log.type != DocumentType.LOG:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Please select SOP + LOG documents.')
        if sop.status != DocumentStatus.APPROVED or log.status != DocumentStatus.APPROVED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail='Only approved documents can be used for analysis.',
            )
        if not sop.approved_json or not log.approved_json:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail='Approved JSON missing for selected documents.',
            )

        findings, summary = comparison_service.compare(sop.approved_json, log.approved_json)

        analysis = Analysis(
            sop_document_id=sop_document_id,
            log_document_id=log_document_id,
            result_json={'findings': findings},
            summary_json=summary,
        )
        db.add(analysis)
        db.commit()
        db.refresh(analysis)
        return analysis

    def list_analyses(self, db: Session) -> list[Analysis]:
        stmt = select(Analysis).order_by(Analysis.created_at.desc())
        return list(db.scalars(stmt).all())

    def get_analysis(self, db: Session, analysis_id: int) -> Analysis:
        analysis = db.get(Analysis, analysis_id)
        if not analysis:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Analysis not found.')
        return analysis


analysis_service = AnalysisService()
