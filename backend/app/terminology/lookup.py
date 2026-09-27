"""CodeLookup: the only way rules see the code tables (DESIGN.md §5.2 `get_code`)."""

from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Code, CodeSet
from app.models import CodeCandidate, CodeSystem


class CodeLookup(Protocol):
    def get_code(self, code: str, code_set_id: str) -> CodeCandidate | None: ...
    def children_of(self, code: str, code_set_id: str) -> list[str]: ...
    def is_billable(self, code: str, code_set_id: str) -> bool: ...


class DbCodeLookup:
    def __init__(self, session: Session) -> None:
        self._session = session

    def _row(self, code: str, code_set_id: str) -> tuple[Code, CodeSystem] | None:
        row = self._session.execute(
            select(Code, CodeSet.system)
            .join(CodeSet, CodeSet.id == Code.code_set_id)
            .where(Code.code_set_id == code_set_id, Code.code == code)
        ).first()
        if row is None:
            return None
        system: CodeSystem = "CPT" if row[1] == "CPT" else "ICD-10-CM"
        return row[0], system

    def get_code(self, code: str, code_set_id: str) -> CodeCandidate | None:
        found = self._row(code, code_set_id)
        if found is None:
            return None
        row, system = found
        return CodeCandidate(
            code=row.code, system=system, description=row.description, score=1.0, sources=[]
        )

    def children_of(self, code: str, code_set_id: str) -> list[str]:
        return list(
            self._session.scalars(
                select(Code.code)
                .where(Code.code_set_id == code_set_id, Code.parent_code == code)
                .order_by(Code.code)
            )
        )

    def is_billable(self, code: str, code_set_id: str) -> bool:
        found = self._row(code, code_set_id)
        return found is not None and found[0].billable
