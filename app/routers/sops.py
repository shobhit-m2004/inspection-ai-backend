from fastapi import APIRouter, Depends, File, UploadFile, HTTPException, status
from sqlalchemy.orm import Session
from typing import Any, List

from app.db.session import get_db
from app.models import SOP, SOPChunk, User
from app.schemas import SOPUploadResponse, SOPListResponse
from app.utils.security import get_current_user_optional
from app.utils.text_extract import extract_text_from_upload
from app.services.embeddings import embed_text
from app.services.faiss_store import add_vector, remove_vector
from app.services.rule_extractor import extract_rules
from app.core.exceptions import BadRequestException, ServiceUnavailableException
from app.core.logging_config import get_logger

router = APIRouter(prefix="/sops", tags=["Standard Operating Procedures"])
logger = get_logger(__name__)


@router.post(
    "/upload",
    response_model=SOPUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload SOP document",
    description="Upload a PDF or TXT file containing Standard Operating Procedure",
    responses={
        400: {"description": "Invalid file format or empty content"},
    },
)
async def upload_sop(
    file: UploadFile = File(..., description="PDF or TXT file containing SOP"),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_optional),
) -> Any:
    """
    Upload a new SOP document.
    
    - **file**: PDF or TXT file (required)
    - Authentication required
    """
    # Validate file type
    if not file.filename:
        raise BadRequestException(detail="File name is required")
    
    if not file.filename.lower().endswith((".pdf", ".txt", ".csv", ".xlsx", ".xls")):
        raise BadRequestException(detail="Only PDF, TXT, CSV, or Excel files are supported")
    
    logger.info(
        "SOP upload started",
        user_id=getattr(current_user, "id", None),
        filename=file.filename,
        size=getattr(file, 'size', 'unknown'),
    )
    
    try:
        # Read and extract content
        content_bytes = await file.read()
        try:
            content = extract_text_from_upload(file.filename, content_bytes)
        except ValueError as e:
            raise BadRequestException(detail=str(e))
        
        if not content or len(content.strip()) == 0:
            raise BadRequestException(detail="SOP content is empty")
        
        # Generate embedding for full document
        embedding = embed_text(content)
        
        # Create SOP record
        sop = SOP(title=file.filename, content=content, embedding_vector=embedding)
        db.add(sop)
        db.commit()
        db.refresh(sop)
        
        # Add to FAISS index
        add_vector("sop", embedding, sop.id)
        
        # Extract deterministic SOP rules
        chunks = extract_rules(content)
        chunk_count = 0
        
        for idx, chunk in enumerate(chunks):
            c_emb = embed_text(chunk)
            sop_chunk = SOPChunk(
                sop_id=sop.id,
                chunk_index=idx,
                content=chunk,
                embedding_vector=c_emb,
            )
            db.add(sop_chunk)
            db.flush()  # ensure sop_chunk.id is assigned
            add_vector("sop_chunk", c_emb, sop_chunk.id)
            chunk_count += 1
        
        db.commit()
        
        logger.info(
            "SOP uploaded successfully",
            sop_id=sop.id,
            chunks=chunk_count,
        )
        
        return {
            "id": sop.id,
            "title": sop.title,
            "uploaded_at": sop.uploaded_at,
            "chunks": chunk_count,
        }
        
    except BadRequestException:
        raise
    except Exception as e:
        db.rollback()
        logger.exception("SOP upload failed", error=str(e))
        raise ServiceUnavailableException(detail="Failed to process SOP document")


@router.get(
    "",
    response_model=List[SOPListResponse],
    summary="List all SOPs",
    description="Get a list of all uploaded SOP documents",
)
def list_sops(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_optional),
) -> Any:
    """
    List all uploaded SOP documents.
    """
    sops = db.query(SOP).order_by(SOP.uploaded_at.desc()).all()
    
    result = []
    for sop in sops:
        chunk_count = db.query(SOPChunk).filter(SOPChunk.sop_id == sop.id).count()
        result.append({
            "id": sop.id,
            "title": sop.title,
            "uploaded_at": sop.uploaded_at,
            "chunk_count": chunk_count,
        })
    
    return result


@router.get(
    "/{sop_id}",
    response_model=SOPUploadResponse,
    summary="Get SOP details",
    description="Get details of a specific SOP document",
    responses={
        404: {"description": "SOP not found"},
    },
)
def get_sop(
    sop_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_optional),
) -> Any:
    """
    Get details of a specific SOP document.
    
    - **sop_id**: SOP document ID
    """
    sop = db.query(SOP).filter(SOP.id == sop_id).first()
    if not sop:
        raise BadRequestException(detail="SOP not found")
    
    chunk_count = db.query(SOPChunk).filter(SOPChunk.sop_id == sop.id).count()
    
    return {
        "id": sop.id,
        "title": sop.title,
        "uploaded_at": sop.uploaded_at,
        "chunks": chunk_count,
    }


@router.delete(
    "/{sop_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete SOP",
    description="Delete an SOP document and its associated chunks and FAISS vectors",
    responses={
        404: {"description": "SOP not found"},
    },
)
def delete_sop(
    sop_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_optional),
) -> None:
    """
    Delete an SOP document and all associated data.

    - **sop_id**: SOP document ID
    
    This will:
    1. Delete all SOP chunks from database
    2. Remove vectors from FAISS index
    3. Delete the SOP document
    4. Delete any compliance results referencing this SOP
    """
    sop = db.query(SOP).filter(SOP.id == sop_id).first()
    if not sop:
        raise BadRequestException(detail="SOP not found")

    logger.info("SOP deletion started", sop_id=sop_id, user_id=getattr(current_user, "id", None))

    try:
        # Delete associated chunks and their FAISS vectors
        chunks = db.query(SOPChunk).filter(SOPChunk.sop_id == sop_id).all()
        for chunk in chunks:
            remove_vector("sop_chunk", chunk.id)
        db.query(SOPChunk).filter(SOPChunk.sop_id == sop_id).delete()

        # Remove SOP vector from FAISS
        remove_vector("sop", sop_id)

        # Delete compliance results referencing this SOP
        from app.models import ComplianceResult
        db.query(ComplianceResult).filter(ComplianceResult.sop_id == sop_id).delete()

        # Delete SOP
        db.delete(sop)
        db.commit()

        logger.info(
            "SOP deleted successfully", 
            sop_id=sop_id, 
            chunks_deleted=len(chunks),
            user_id=getattr(current_user, "id", None)
        )
    except Exception as e:
        db.rollback()
        logger.exception("SOP deletion failed", error=str(e))
        raise ServiceUnavailableException(detail="Failed to delete SOP document")

