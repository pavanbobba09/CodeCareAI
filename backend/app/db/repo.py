"""Read helpers over the db tables. No business logic here."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import CodeSet


def code_set_ids(session: Session) -> list[str]:
    return list(session.scalars(select(CodeSet.id).order_by(CodeSet.id)))
