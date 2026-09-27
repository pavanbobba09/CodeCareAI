"""Fill codes.embedding for one code set (text = official description)."""

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.db.models import Code
from app.terminology.embedder import Embedder

BATCH = 1024


def embed_code_set(session: Session, code_set_id: str, embedder: Embedder) -> int:
    """Embed codes that have no vector yet. Commits per batch so a rerun resumes."""
    done = 0
    while True:
        rows = session.execute(
            select(Code.code, Code.description)
            .where(Code.code_set_id == code_set_id, Code.embedding.is_(None))
            .order_by(Code.code)
            .limit(BATCH)
        ).all()
        if not rows:
            return done
        vectors = embedder.embed([desc for _, desc in rows])
        session.execute(
            update(Code),
            [
                {"code_set_id": code_set_id, "code": code, "embedding": vec}
                for (code, _), vec in zip(rows, vectors, strict=True)
            ],
        )
        session.commit()
        done += len(rows)
