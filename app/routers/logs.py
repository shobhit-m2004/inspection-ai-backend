from fastapi import APIRouter, Depends, File, UploadFile, status
from sqlalchemy.orm import Session
from typing import Any, List

from app.db.session import get_db
from app.models import Log, LogChunk, User
from app.schemas import LogUploadResponse, LogListResponse
from app.utils.security import get_current_user_optional
from app.utils.text_extract import extract_text_from_upload
from app.services.embeddings import embed_text
from app.services.faiss_store import add_vector, remove_vector
from app.services.chunking import chunk_text
from app.core.exceptions import BadRequestException, ServiceUnavailableException
from app.core.logging_config import get_logger

router = APIRouter(prefix="/logs", tags=["Operational Logs"])
logger = get_logger(__name__)


@router.post(
    "/upload",
    response_model=LogUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload operational log",
    description="Upload a PDF or TXT file containing operational log data",
    responses={
        400: {"description": "Invalid file format or empty content"},
    },
)
async def upload_log(
    file: UploadFile = File(..., description="PDF or TXT file containing operational log"),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_optional),
) -> Any:
    """
    Upload a new operational log document.
    
    - **file**: PDF or TXT file (required)
    - Authentication required
    """
    if not file.filename:
        raise BadRequestException(detail="File name is required")
    
    if not file.filename.lower().endswith((".pdf", ".txt", ".csv", ".xlsx", ".xls")):
        raise BadRequestException(detail="Only PDF, TXT, CSV, or Excel files are supported")
    
    logger.info(
        "Log upload started",
        user_id=getattr(current_user, "id", None),
        filename=file.filename,
    )
    
    try:
        content_bytes = await file.read()
        try:
            content = extract_text_from_upload(file.filename, content_bytes)
        except ValueError as e:
            raise BadRequestException(detail=str(e))
        
        if not content or len(content.strip()) == 0:
            raise BadRequestException(detail="Log content is empty")
        
        embedding = embed_text(content)
        
        log = Log(title=file.filename, content=content, embedding_vector=embedding)
        db.add(log)
        db.commit()
        db.refresh(log)
        
        add_vector("log", embedding, log.id)
        
        chunks = chunk_text(content)
        chunk_count = 0
        
        for idx, chunk in enumerate(chunks):
            c_emb = embed_text(chunk)
            log_chunk = LogChunk(
                log_id=log.id,
                chunk_index=idx,
                content=chunk,
                embedding_vector=c_emb,
            )
            db.add(log_chunk)
            db.flush()  # ensure log_chunk.id is assigned
            add_vector("log_chunk", c_emb, log_chunk.id)
            chunk_count += 1
        
        db.commit()
        
        logger.info(
            "Log uploaded successfully",
            log_id=log.id,
            chunks=chunk_count,
        )
        
        return {
            "id": log.id,
            "title": log.title,
            "uploaded_at": log.uploaded_at,
            "chunks": chunk_count,
        }
        
    except BadRequestException:
        raise
    except Exception as e:
        db.rollback()
        logger.exception("Log upload failed", error=str(e))
        raise ServiceUnavailableException(detail="Failed to process log document")


@router.get(
    "",
    response_model=List[LogListResponse],
    summary="List all logs",
    description="Get a list of all uploaded operational logs",
)
def list_logs(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_optional),
) -> Any:
    """
    List all uploaded operational log documents.
    """
    logs = db.query(Log).order_by(Log.uploaded_at.desc()).all()
    
    result = []
    for log in logs:
        chunk_count = db.query(LogChunk).filter(LogChunk.log_id == log.id).count()
        result.append({
            "id": log.id,
            "title": log.title,
            "uploaded_at": log.uploaded_at,
            "chunk_count": chunk_count,
        })
    
    return result


@router.get(
    "/{log_id}",
    response_model=LogUploadResponse,
    summary="Get log details",
    description="Get details of a specific log document",
    responses={
        404: {"description": "Log not found"},
    },
)
def get_log(
    log_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_optional),
) -> Any:
    """
    Get details of a specific log document.
    """
    log = db.query(Log).filter(Log.id == log_id).first()
    if not log:
        raise BadRequestException(detail="Log not found")
    
    chunk_count = db.query(LogChunk).filter(LogChunk.log_id == log.id).count()
    
    return {
        "id": log.id,
        "title": log.title,
        "uploaded_at": log.uploaded_at,
        "chunks": chunk_count,
    }


@router.delete(
    "/{log_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete log",
    description="Delete a log document and its associated chunks and FAISS vectors",
    responses={
        404: {"description": "Log not found"},
    },
)
def delete_log(
    log_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_optional),
) -> None:
    """
    Delete a log document and all associated data.

    - **log_id**: Log document ID
    
    This will:
    1. Delete all log chunks from database
    2. Remove vectors from FAISS index
    3. Delete the log document
    4. Delete any compliance results referencing this log
    """
    log = db.query(Log).filter(Log.id == log_id).first()
    if not log:
        raise BadRequestException(detail="Log not found")

    logger.info("Log deletion started", log_id=log_id, user_id=getattr(current_user, "id", None))

    try:
        # Delete associated chunks and their FAISS vectors
        chunks = db.query(LogChunk).filter(LogChunk.log_id == log_id).all()
        for chunk in chunks:
            remove_vector("log_chunk", chunk.id)
        db.query(LogChunk).filter(LogChunk.log_id == log_id).delete()

        # Remove log vector from FAISS
        remove_vector("log", log_id)

        # Delete compliance results referencing this log
        from app.models import ComplianceResult
        db.query(ComplianceResult).filter(ComplianceResult.log_id == log_id).delete()

        # Delete log
        db.delete(log)
        db.commit()

        logger.info(
            "Log deleted successfully", 
            log_id=log_id, 
            chunks_deleted=len(chunks),
            user_id=getattr(current_user, "id", None)
        )
    except Exception as e:
        db.rollback()
        logger.exception("Log deletion failed", error=str(e))
        raise ServiceUnavailableException(detail="Failed to delete log document")

