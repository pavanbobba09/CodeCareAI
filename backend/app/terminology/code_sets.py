"""Pick the code sets valid on a visit date (DESIGN.md §4.1 step 4).

ICD-10-CM is required. CPT is optional: a visit date with no CPT set loaded is valid,
and the CPT-dependent rules are skipped for it.
"""

from datetime import date

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.db.models import CodeSet
from app.models import CodeSetSelection, CodeSystem


class CodeSetMissingError(Exception):
    """No loaded code set covers the visit date; the API maps this to 409 CODE_SET_MISSING."""

    def __init__(self, system: CodeSystem, visit_date: date) -> None:
        super().__init__(f"No {system} code set covers visit date {visit_date.isoformat()}.")
        self.system = system
        self.visit_date = visit_date


def _find(session: Session, system: CodeSystem, visit_date: date) -> str | None:
    stmt = (
        select(CodeSet.id)
        .where(
            CodeSet.system == system,
            CodeSet.valid_from <= visit_date,
            or_(CodeSet.valid_to.is_(None), CodeSet.valid_to >= visit_date),
        )
        .order_by(CodeSet.valid_from.desc())
        .limit(1)
    )
    return session.scalar(stmt)


def resolve_code_set(session: Session, system: CodeSystem, visit_date: date) -> str:
    code_set_id = _find(session, system, visit_date)
    if code_set_id is None:
        raise CodeSetMissingError(system, visit_date)
    return code_set_id


def resolve_code_sets(session: Session, visit_date: date) -> CodeSetSelection:
    return CodeSetSelection(
        icd10cm=resolve_code_set(session, "ICD-10-CM", visit_date),
        cpt=_find(session, "CPT", visit_date),
    )
