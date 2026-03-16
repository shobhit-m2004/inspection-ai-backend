from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.document import AssistantMessage, ReviewSession
from app.models.enums import SessionStatus
from app.schemas.review import AssistantRequest, AssistantResponse
from app.services.document_service import document_service
from app.workflows.langgraph_workflow import run_review_graph


class AssistantService:
    def run_assistant(
        self,
        db: Session,
        document_id: int,
        payload: AssistantRequest,
    ) -> AssistantResponse:
        document = document_service.get_document(db, document_id)

        review_session = self._resolve_review_session(db, document_id, payload.review_session_id)

        current_json = payload.current_json or document.extracted_json or document.approved_json
        if current_json is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail='No extracted JSON available yet. Run extraction first.',
            )

        selected_context = (review_session.selected_parameters or {}).get('selected_parameters', [])

        state = {
            'document_type': document.type.value,
            'raw_text': document.raw_text,
            'current_json': current_json,
            'selected_parameters': selected_context,
            'user_message': payload.message,
            'approved': False,
        }

        result = run_review_graph(state)

        updated_json = result.get('updated_json') if result.get('changed') else None
        if result.get('changed') and updated_json:
            document.extracted_json = updated_json
            db.add(document)

        db.add(
            AssistantMessage(
                review_session_id=review_session.id,
                role='user',
                message=payload.message,
                updated_json_snapshot=None,
            )
        )
        db.add(
            AssistantMessage(
                review_session_id=review_session.id,
                role='assistant',
                message=result.get('assistant_message', ''),
                updated_json_snapshot=updated_json,
            )
        )
        db.commit()

        return AssistantResponse(
            review_session_id=review_session.id,
            message=result.get('assistant_message', ''),
            updated_json=updated_json,
            changed=bool(result.get('changed', False)),
        )

    def _resolve_review_session(
        self,
        db: Session,
        document_id: int,
        review_session_id: int | None,
    ) -> ReviewSession:
        if review_session_id:
            session = document_service.get_review_session(db, review_session_id)
            if session.document_id != document_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail='Review session does not belong to requested document.',
                )
            return session

        session = document_service.get_latest_review_session(db, document_id)
        if session:
            return session

        session = ReviewSession(
            document_id=document_id,
            selected_parameters={'mode': 'auto', 'selected_parameters': []},
            session_status=SessionStatus.ACTIVE,
        )
        db.add(session)
        db.commit()
        db.refresh(session)
        return session


assistant_service = AssistantService()
