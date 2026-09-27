"""Initial schema: all tables from DESIGN.md §5.3.

Revision ID: 0001
Revises:
Create Date: 2026-09-26
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    op.create_table(
        "code_sets",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("system", sa.String(16), nullable=False),
        sa.Column("valid_from", sa.Date(), nullable=False),
        sa.Column("valid_to", sa.Date(), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.CheckConstraint("system IN ('ICD-10-CM', 'CPT')", name="ck_code_sets_system"),
    )
    op.create_index("ix_code_sets_validity", "code_sets", ["valid_from", "valid_to"])

    op.create_table(
        "codes",
        sa.Column("code_set_id", sa.String(64), sa.ForeignKey("code_sets.id"), primary_key=True),
        sa.Column("code", sa.String(16), primary_key=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("billable", sa.Boolean(), nullable=False),
        sa.Column("parent_code", sa.String(16), nullable=True),
        sa.Column(
            "tabular_notes",
            postgresql.JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("embedding", Vector(384), nullable=True),
        sa.Column(
            "tsv",
            postgresql.TSVECTOR(),
            sa.Computed("to_tsvector('english', description)", persisted=True),
            nullable=False,
        ),
    )
    op.create_index("ix_codes_tsv", "codes", ["tsv"], postgresql_using="gin")
    op.create_index(
        "ix_codes_embedding",
        "codes",
        ["embedding"],
        postgresql_using="hnsw",
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )
    op.create_index("ix_codes_parent_code", "codes", ["parent_code"])

    op.create_table(
        "index_terms",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("code_set_id", sa.String(64), sa.ForeignKey("code_sets.id"), nullable=False),
        sa.Column("term", sa.Text(), nullable=False),
        sa.Column("path", sa.Text(), nullable=False),
        sa.Column("code", sa.String(16), nullable=False),
    )
    op.create_index(
        "ix_index_terms_term_trgm",
        "index_terms",
        ["term"],
        postgresql_using="gin",
        postgresql_ops={"term": "gin_trgm_ops"},
    )
    op.create_index("ix_index_terms_code_set_code", "index_terms", ["code_set_id", "code"])

    op.create_table(
        "abbreviations",
        sa.Column("abbr", sa.String(32), primary_key=True),
        sa.Column("expansion", sa.Text(), nullable=False),
    )

    op.create_table(
        "ncci_ptp",
        sa.Column("column1_code", sa.String(16), primary_key=True),
        sa.Column("column2_code", sa.String(16), primary_key=True),
        sa.Column("valid_from", sa.Date(), primary_key=True),
        sa.Column("valid_to", sa.Date(), nullable=True),
        sa.Column("modifier_allowed", sa.Boolean(), nullable=False),
    )

    op.create_table(
        "notes",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("visit_date", sa.Date(), nullable=False),
        sa.Column("patient_type", sa.String(16), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("sentences", postgresql.JSONB(), nullable=False),
        sa.Column("parent_note_id", sa.String(36), sa.ForeignKey("notes.id"), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint("patient_type IN ('new', 'established')", name="ck_notes_patient_type"),
    )

    op.create_table(
        "analyses",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("note_id", sa.String(36), sa.ForeignKey("notes.id"), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("result_json", postgresql.JSONB(), nullable=False),
        sa.Column("model", sa.Text(), nullable=False),
        sa.Column("prompt_version", sa.String(32), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint("status IN ('completed', 'failed')", name="ck_analyses_status"),
    )
    op.create_index("ix_analyses_note_created", "analyses", ["note_id", "created_at"])

    op.create_table(
        "reviews",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("analysis_id", sa.String(36), sa.ForeignKey("analyses.id"), nullable=False),
        sa.Column("suggestion_id", sa.String(64), nullable=False),
        sa.Column("action", sa.String(16), nullable=False),
        sa.Column("replacement_code", sa.String(16), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint("action IN ('accept', 'edit', 'reject')", name="ck_reviews_action"),
    )
    op.create_index("ix_reviews_analysis_suggestion", "reviews", ["analysis_id", "suggestion_id"])

    # Reviews are append-only (CLAUDE.md rule 8): block UPDATE, DELETE, and TRUNCATE.
    op.execute(
        """
        CREATE FUNCTION reviews_append_only() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'reviews is append-only: % is not allowed', TG_OP;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER reviews_no_update_delete
        BEFORE UPDATE OR DELETE ON reviews
        FOR EACH ROW EXECUTE FUNCTION reviews_append_only()
        """
    )
    op.execute(
        """
        CREATE TRIGGER reviews_no_truncate
        BEFORE TRUNCATE ON reviews
        FOR EACH STATEMENT EXECUTE FUNCTION reviews_append_only()
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS reviews_no_truncate ON reviews")
    op.execute("DROP TRIGGER IF EXISTS reviews_no_update_delete ON reviews")
    op.execute("DROP FUNCTION IF EXISTS reviews_append_only()")
    for table in (
        "reviews",
        "analyses",
        "notes",
        "ncci_ptp",
        "abbreviations",
        "index_terms",
        "codes",
        "code_sets",
    ):
        op.drop_table(table)
