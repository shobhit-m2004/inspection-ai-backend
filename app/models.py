from sqlalchemy import Column, Integer, String, DateTime, Float, ForeignKey, Text
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import relationship

from app.db.session import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(120), nullable=False)
    email = Column(String(200), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class SOP(Base):
    __tablename__ = "sops"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)
    embedding_vector = Column(ARRAY(Float), nullable=True)
    uploaded_at = Column(DateTime(timezone=True), server_default=func.now())

    chunks = relationship("SOPChunk", back_populates="sop", cascade="all, delete-orphan")

class Log(Base):
    __tablename__ = "logs"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)
    embedding_vector = Column(ARRAY(Float), nullable=True)
    uploaded_at = Column(DateTime(timezone=True), server_default=func.now())

    chunks = relationship("LogChunk", back_populates="log", cascade="all, delete-orphan")

class SOPChunk(Base):
    __tablename__ = "sop_chunks"

    id = Column(Integer, primary_key=True, index=True)
    sop_id = Column(Integer, ForeignKey("sops.id"), nullable=False)
    chunk_index = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    embedding_vector = Column(ARRAY(Float), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    sop = relationship("SOP", back_populates="chunks")

class LogChunk(Base):
    __tablename__ = "log_chunks"

    id = Column(Integer, primary_key=True, index=True)
    log_id = Column(Integer, ForeignKey("logs.id"), nullable=False)
    chunk_index = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    embedding_vector = Column(ARRAY(Float), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    log = relationship("Log", back_populates="chunks")

class ComplianceResult(Base):
    __tablename__ = "compliance_results"

    id = Column(Integer, primary_key=True, index=True)
    sop_id = Column(Integer, ForeignKey("sops.id"), nullable=False)
    log_id = Column(Integer, ForeignKey("logs.id"), nullable=False)
    similarity_score = Column(Float, nullable=False)
    gap_summary = Column(Text, nullable=False)
    analyzed_at = Column(DateTime(timezone=True), server_default=func.now())

    sop = relationship("SOP")
    log = relationship("Log")
