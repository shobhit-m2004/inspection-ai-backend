from __future__ import annotations

import shutil
import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.document import Document, ReviewSession
from app.models.enums import DocumentStatus, DocumentType, SessionStatus
from app.services.extraction_service import extraction_service
from app.services.normalization_service import normalization_service
from app.utils.document_parser import DocumentParseError, extract_text_from_file

settings = get_settings()


class DocumentService:
    def upload_document(self, db: Session, document_type: DocumentType, file: UploadFile) -> Document:
        if not file.filename:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Filename is required.')

        storage_name = f"{uuid.uuid4().hex}_{Path(file.filename).name}"
        file_path = settings.uploads_dir / storage_name

        with file_path.open('wb') as target:
            shutil.copyfileobj(file.file, target)

        try:
            raw_text = extract_text_from_file(file_path)
        except DocumentParseError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

        if not raw_text.strip():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='No text extracted from document.')

        document = Document(
            type=document_type,
            original_filename=file.filename,
            storage_path=str(file_path),
            raw_text=raw_text,
            status=DocumentStatus.DRAFT,
        )
        db.add(document)
        db.commit()
        db.refresh(document)
        return document

    def list_documents(
        self,
        db: Session,
        document_type: DocumentType | None = None,
        status_filter: DocumentStatus | None = None,
    ) -> list[Document]:
        stmt = select(Document)
        if document_type:
            stmt = stmt.where(Document.type == document_type)
        if status_filter:
            stmt = stmt.where(Document.status == status_filter)
        stmt = stmt.order_by(Document.created_at.desc())
        return list(db.scalars(stmt).all())

    def get_document(self, db: Session, document_id: int) -> Document:
        document = db.get(Document, document_id)
        if not document:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Document not found.')
        return document

    def extract_document(
        self,
        db: Session,
        document: Document,
        mode: str,
        selected_parameters: list[str],
    ) -> tuple[ReviewSession, dict, list[str]]:
        normalized_selected = (
            normalization_service.normalize_selected_parameters(selected_parameters) if mode == 'manual' else []
        )

        extracted_json, warnings = extraction_service.extract_structured(
            document_type=document.type,
            raw_text=document.raw_text,
            selected_parameters=normalized_selected,
            mode=mode,
        )
        document.extracted_json = extracted_json

        review_session = ReviewSession(
            document_id=document.id,
            selected_parameters={
                'mode': mode,
                'selected_parameters': normalized_selected,
            },
            session_status=SessionStatus.ACTIVE,
        )
        db.add(review_session)
        db.add(document)
        db.commit()
        db.refresh(review_session)
        db.refresh(document)

        return review_session, extracted_json, warnings

    def approve_document(self, db: Session, document: Document, approved_json: dict | None) -> Document:
        final_json = approved_json or document.extracted_json
        if not final_json:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail='No extracted JSON available. Run extraction first.',
            )

        document.approved_json = final_json
        document.status = DocumentStatus.APPROVED
        db.add(document)

        active_sessions = db.scalars(
            select(ReviewSession).where(
                ReviewSession.document_id == document.id,
                ReviewSession.session_status == SessionStatus.ACTIVE,
            )
        ).all()
        for session in active_sessions:
            session.session_status = SessionStatus.CLOSED
            db.add(session)

        db.commit()
        db.refresh(document)
        return document

    def get_review_session(self, db: Session, review_session_id: int) -> ReviewSession:
        session = db.get(ReviewSession, review_session_id)
        if not session:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Review session not found.')
        return session

    def get_latest_review_session(self, db: Session, document_id: int) -> ReviewSession | None:
        stmt = (
            select(ReviewSession)
            .where(ReviewSession.document_id == document_id)
            .order_by(ReviewSession.created_at.desc())
        )
        return db.scalars(stmt).first()


document_service = DocumentService()
