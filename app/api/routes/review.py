from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.review import AssistantRequest, AssistantResponse
from app.services.assistant_service import assistant_service

router = APIRouter()


@router.post('/{document_id}/assistant', response_model=AssistantResponse)
def assistant_reply(document_id: int, payload: AssistantRequest, db: Session = Depends(get_db)):
    return assistant_service.run_assistant(db=db, document_id=document_id, payload=payload)
