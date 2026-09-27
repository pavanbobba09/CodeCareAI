"""SQLAlchemy tables from DESIGN.md §5.3. Schema changes go through Alembic."""

from datetime import date, datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Computed,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

EMBEDDING_DIM = 384  # BAAI/bge-small-en-v1.5


class Base(DeclarativeBase):
    pass


class CodeSet(Base):
    __tablename__ = "code_sets"
    __table_args__ = (
        CheckConstraint("system IN ('ICD-10-CM', 'CPT')", name="ck_code_sets_system"),
        Index("ix_code_sets_validity", "valid_from", "valid_to"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)  # e.g. ICD10CM-FY2027
    system: Mapped[str] = mapped_column(String(16))
    valid_from: Mapped[date] = mapped_column(Date)
    valid_to: Mapped[date | None] = mapped_column(Date)
    source_url: Mapped[str | None] = mapped_column(Text)


class Code(Base):
    __tablename__ = "codes"
    __table_args__ = (
        Index("ix_codes_tsv", "tsv", postgresql_using="gin"),
        Index(
            "ix_codes_embedding",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
        Index("ix_codes_parent_code", "parent_code"),
    )

    code_set_id: Mapped[str] = mapped_column(ForeignKey("code_sets.id"), primary_key=True)
    code: Mapped[str] = mapped_column(String(16), primary_key=True)
    description: Mapped[str] = mapped_column(Text)
    billable: Mapped[bool] = mapped_column(Boolean)
    parent_code: Mapped[str | None] = mapped_column(String(16))
    # {"excludes1": [...], "use_additional": [...], "code_first": [...]}
    tabular_notes: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default="{}")
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIM))
    tsv: Mapped[str] = mapped_column(
        TSVECTOR, Computed("to_tsvector('english', description)", persisted=True)
    )


class IndexTerm(Base):
    __tablename__ = "index_terms"
    __table_args__ = (
        Index(
            "ix_index_terms_term_trgm",
            "term",
            postgresql_using="gin",
            postgresql_ops={"term": "gin_trgm_ops"},
        ),
        Index("ix_index_terms_code_set_code", "code_set_id", "code"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code_set_id: Mapped[str] = mapped_column(ForeignKey("code_sets.id"))
    term: Mapped[str] = mapped_column(Text)
    path: Mapped[str] = mapped_column(Text)  # main term > subterm > ...
    code: Mapped[str] = mapped_column(String(16))


class Abbreviation(Base):
    __tablename__ = "abbreviations"

    abbr: Mapped[str] = mapped_column(String(32), primary_key=True)
    expansion: Mapped[str] = mapped_column(Text)


class NcciPtp(Base):
    __tablename__ = "ncci_ptp"

    column1_code: Mapped[str] = mapped_column(String(16), primary_key=True)
    column2_code: Mapped[str] = mapped_column(String(16), primary_key=True)
    valid_from: Mapped[date] = mapped_column(Date, primary_key=True)
    valid_to: Mapped[date | None] = mapped_column(Date)
    modifier_allowed: Mapped[bool] = mapped_column(Boolean)


class NoteRow(Base):
    __tablename__ = "notes"
    __table_args__ = (
        CheckConstraint("patient_type IN ('new', 'established')", name="ck_notes_patient_type"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    visit_date: Mapped[date] = mapped_column(Date)
    patient_type: Mapped[str] = mapped_column(String(16))
    text: Mapped[str] = mapped_column(Text)
    sentences: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)
    parent_note_id: Mapped[str | None] = mapped_column(ForeignKey("notes.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AnalysisRow(Base):
    __tablename__ = "analyses"
    __table_args__ = (
        CheckConstraint("status IN ('completed', 'failed')", name="ck_analyses_status"),
        Index("ix_analyses_note_created", "note_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    note_id: Mapped[str] = mapped_column(ForeignKey("notes.id"))
    status: Mapped[str] = mapped_column(String(16))
    result_json: Mapped[dict[str, Any]] = mapped_column(JSONB)
    model: Mapped[str] = mapped_column(Text)
    prompt_version: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ReviewRow(Base):
    """Append-only. A database trigger rejects UPDATE and DELETE (migration 0001)."""

    __tablename__ = "reviews"
    __table_args__ = (
        CheckConstraint("action IN ('accept', 'edit', 'reject')", name="ck_reviews_action"),
        Index("ix_reviews_analysis_suggestion", "analysis_id", "suggestion_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    analysis_id: Mapped[str] = mapped_column(ForeignKey("analyses.id"))
    suggestion_id: Mapped[str] = mapped_column(String(64))
    action: Mapped[str] = mapped_column(String(16))
    replacement_code: Mapped[str | None] = mapped_column(String(16))
    reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
