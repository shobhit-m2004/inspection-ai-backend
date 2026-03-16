from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile

from app.db.session import get_db
from app.models.document import ReviewSession
from app.models.enums import DocumentStatus, DocumentType
from app.schemas.document import (
    ApproveRequest,
    ApproveResponse,
    DocumentDetail,
    DocumentSummary,
    DocumentUploadResponse,
    ExtractRequest,
    ExtractResponse,
)
from app.schemas.review import ReviewSessionRead
from app.services.document_service import document_service

router = APIRouter()


@router.post('/upload', response_model=DocumentUploadResponse)
def upload_document(
    document_type: DocumentType = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    document = document_service.upload_document(db=db, document_type=document_type, file=file)
    return document


@router.get('', response_model=list[DocumentSummary])
def list_documents(
    type: DocumentType | None = Query(default=None),
    status: DocumentStatus | None = Query(default=None),
    db: Session = Depends(get_db),
):
    return document_service.list_documents(db=db, document_type=type, status_filter=status)


@router.get('/{document_id}', response_model=DocumentDetail)
def get_document(document_id: int, db: Session = Depends(get_db)):
    return document_service.get_document(db, document_id)


@router.post('/{document_id}/extract', response_model=ExtractResponse)
def extract_document(document_id: int, payload: ExtractRequest, db: Session = Depends(get_db)):
    document = document_service.get_document(db, document_id)
    review_session, extracted_json, warnings = document_service.extract_document(
        db=db,
        document=document,
        mode=payload.mode,
        selected_parameters=payload.selected_parameters,
    )
    return ExtractResponse(
        document_id=document_id,
        review_session_id=review_session.id,
        extracted_json=extracted_json,
        warnings=warnings,
    )


@router.post('/{document_id}/approve', response_model=ApproveResponse)
def approve_document(document_id: int, payload: ApproveRequest, db: Session = Depends(get_db)):
    document = document_service.get_document(db, document_id)
    document = document_service.approve_document(db=db, document=document, approved_json=payload.approved_json)
    return ApproveResponse(document_id=document.id, status=document.status, approved_json=document.approved_json or {})


@router.get('/{document_id}/review/latest', response_model=ReviewSessionRead)
def latest_review(document_id: int, db: Session = Depends(get_db)):
    stmt = (
        select(ReviewSession)
        .where(ReviewSession.document_id == document_id)
        .options(selectinload(ReviewSession.messages))
        .order_by(ReviewSession.created_at.desc())
    )
    session = db.scalars(stmt).first()
    if not session:
        return ReviewSessionRead(
            id=0,
            document_id=document_id,
            selected_parameters={'mode': 'auto', 'selected_parameters': []},
            session_status='active',
            created_at=document_service.get_document(db, document_id).created_at,
            updated_at=None,
            messages=[],
        )
    return session
