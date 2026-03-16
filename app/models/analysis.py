from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, JSON, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base


class Analysis(Base):
    __tablename__ = 'analyses'

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    sop_document_id: Mapped[int] = mapped_column(ForeignKey('documents.id', ondelete='CASCADE'), index=True)
    log_document_id: Mapped[int] = mapped_column(ForeignKey('documents.id', ondelete='CASCADE'), index=True)
    result_json: Mapped[dict] = mapped_column(JSON)
    summary_json: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


Index('ix_analyses_sop_log', Analysis.sop_document_id, Analysis.log_document_id)
