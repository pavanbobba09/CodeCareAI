"""Read and write helpers over the db tables. No business logic here.

Reviews are append-only (CLAUDE.md rule 8): there is an insert and reads, and no update or
delete function for `reviews`. A db trigger also rejects UPDATE and DELETE.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AnalysisRow, CodeSet, NoteRow, ReviewRow
from app.models import AnalysisResult, Note, NoteCreate, ReviewEvent, ReviewRequest, Sentence


def code_set_ids(session: Session) -> list[str]:
    return list(session.scalars(select(CodeSet.id).order_by(CodeSet.id)))


def _to_note(row: NoteRow) -> Note:
    return Note(
        id=row.id,
        visit_date=row.visit_date,
        patient_type="new" if row.patient_type == "new" else "established",
        text=row.text,
        sentences=[Sentence.model_validate(s) for s in row.sentences],
        parent_note_id=row.parent_note_id,
        created_at=row.created_at,
    )


def note_exists(session: Session, note_id: str) -> bool:
    return session.get(NoteRow, note_id) is not None


def insert_note(session: Session, body: NoteCreate, sentences: list[Sentence]) -> Note:
    row = NoteRow(
        id=str(uuid.uuid4()),
        visit_date=body.visit_date,
        patient_type=body.patient_type,
        text=body.text,
        sentences=[s.model_dump() for s in sentences],
        parent_note_id=body.parent_note_id,
    )
    session.add(row)
    session.flush()
    session.refresh(row)  # server default created_at
    return _to_note(row)


def get_note(session: Session, note_id: str) -> Note | None:
    row = session.get(NoteRow, note_id)
    return None if row is None else _to_note(row)


def insert_analysis(session: Session, result: AnalysisResult) -> None:
    session.add(
        AnalysisRow(
            id=result.analysis_id,
            note_id=result.note_id,
            status=result.status,
            result_json=result.model_dump(mode="json"),
            model=result.model,
            prompt_version=result.prompt_version,
            created_at=result.created_at,
        )
    )
    session.flush()


def get_analysis(session: Session, analysis_id: str) -> AnalysisResult | None:
    row = session.get(AnalysisRow, analysis_id)
    return None if row is None else AnalysisResult.model_validate(row.result_json)


def list_analyses(session: Session, note_id: str) -> list[AnalysisResult]:
    """Newest first."""
    rows = session.scalars(
        select(AnalysisRow)
        .where(AnalysisRow.note_id == note_id)
        .order_by(AnalysisRow.created_at.desc(), AnalysisRow.id)
    )
    return [AnalysisResult.model_validate(r.result_json) for r in rows]


def _to_review(row: ReviewRow) -> ReviewEvent:
    return ReviewEvent.model_validate(row, from_attributes=True)


def insert_review(
    session: Session, analysis_id: str, suggestion_id: str, body: ReviewRequest
) -> ReviewEvent:
    row = ReviewRow(
        id=str(uuid.uuid4()),
        analysis_id=analysis_id,
        suggestion_id=suggestion_id,
        action=body.action,
        replacement_code=body.replacement_code,
        reason=body.reason,
    )
    session.add(row)
    session.flush()
    session.refresh(row)  # server default created_at
    return _to_review(row)


def list_reviews(session: Session, analysis_ids: list[str]) -> list[ReviewEvent]:
    """Oldest first."""
    if not analysis_ids:
        return []
    rows = session.scalars(
        select(ReviewRow)
        .where(ReviewRow.analysis_id.in_(analysis_ids))
        .order_by(ReviewRow.created_at, ReviewRow.id)
    )
    return [_to_review(r) for r in rows]


def previous_versions(session: Session, note: Note) -> list[str]:
    """Ids of the notes this one was revised from, oldest first."""
    chain: list[str] = []
    parent = note.parent_note_id
    while parent is not None and parent not in chain:
        chain.append(parent)
        row = session.get(NoteRow, parent)
        parent = row.parent_note_id if row is not None else None
    return list(reversed(chain))


def later_versions(session: Session, note_id: str) -> list[str]:
    """Ids of every note revised from this one (directly or through later versions)."""
    found: list[NoteRow] = []
    frontier = [note_id]
    while frontier:
        rows = list(session.scalars(select(NoteRow).where(NoteRow.parent_note_id.in_(frontier))))
        rows = [r for r in rows if r.id not in {f.id for f in found}]
        found += rows
        frontier = [r.id for r in rows]
    return [r.id for r in sorted(found, key=lambda r: (r.created_at, r.id))]
