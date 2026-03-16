from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Index, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base
from app.models.enums import DocumentStatus, DocumentType, SessionStatus


class Document(Base):
    __tablename__ = 'documents'

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    type: Mapped[DocumentType] = mapped_column(Enum(DocumentType, name='document_type'), index=True)
    original_filename: Mapped[str] = mapped_column(String(255))
    storage_path: Mapped[str] = mapped_column(String(512))
    raw_text: Mapped[str] = mapped_column(Text)
    extracted_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    approved_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status: Mapped[DocumentStatus] = mapped_column(
        Enum(DocumentStatus, name='document_status'), default=DocumentStatus.DRAFT, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    review_sessions: Mapped[list['ReviewSession']] = relationship(
        back_populates='document', cascade='all, delete-orphan'
    )


class ReviewSession(Base):
    __tablename__ = 'review_sessions'

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    document_id: Mapped[int] = mapped_column(ForeignKey('documents.id', ondelete='CASCADE'), index=True)
    selected_parameters: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    session_status: Mapped[SessionStatus] = mapped_column(
        Enum(SessionStatus, name='session_status'), default=SessionStatus.ACTIVE
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    document: Mapped['Document'] = relationship(back_populates='review_sessions')
    messages: Mapped[list['AssistantMessage']] = relationship(
        back_populates='review_session', cascade='all, delete-orphan'
    )


class AssistantMessage(Base):
    __tablename__ = 'assistant_messages'

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    review_session_id: Mapped[int] = mapped_column(ForeignKey('review_sessions.id', ondelete='CASCADE'), index=True)
    role: Mapped[str] = mapped_column(String(20))
    message: Mapped[str] = mapped_column(Text)
    updated_json_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    review_session: Mapped['ReviewSession'] = relationship(back_populates='messages')


Index('ix_documents_type_status', Document.type, Document.status)
