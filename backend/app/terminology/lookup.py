"""CodeLookup: the only way rules see the code tables (DESIGN.md §5.2 `get_code`)."""

from dataclasses import dataclass
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


@dataclass(frozen=True)
class CodeRecord:
    code: str
    system: CodeSystem
    description: str
    billable: bool
    parent_code: str | None


class InMemoryCodeLookup:
    """CodeLookup over preloaded records, so rules stay pure (no db inside a rule)."""

    def __init__(self, records: dict[tuple[str, str], CodeRecord]) -> None:
        self._records = records

    def get_code(self, code: str, code_set_id: str) -> CodeCandidate | None:
        rec = self._records.get((code_set_id, code))
        if rec is None:
            return None
        return CodeCandidate(
            code=rec.code, system=rec.system, description=rec.description, score=1.0, sources=[]
        )

    def children_of(self, code: str, code_set_id: str) -> list[str]:
        return sorted(
            rec.code
            for (cs, _), rec in self._records.items()
            if cs == code_set_id and rec.parent_code == code
        )

    def is_billable(self, code: str, code_set_id: str) -> bool:
        rec = self._records.get((code_set_id, code))
        return rec is not None and rec.billable


def preload_lookup(session: Session, wanted: dict[str, set[str]]) -> InMemoryCodeLookup:
    """Load exactly the given codes (code_set_id -> codes) into memory."""
    records: dict[tuple[str, str], CodeRecord] = {}
    for code_set_id, codes in wanted.items():
        rows = session.execute(
            select(Code, CodeSet.system)
            .join(CodeSet, CodeSet.id == Code.code_set_id)
            .where(Code.code_set_id == code_set_id, Code.code.in_(sorted(codes)))
        ).all()
        for row, system in rows:
            records[(code_set_id, row.code)] = CodeRecord(
                code=row.code,
                system="CPT" if system == "CPT" else "ICD-10-CM",
                description=row.description,
                billable=row.billable,
                parent_code=row.parent_code,
            )
    return InMemoryCodeLookup(records)
