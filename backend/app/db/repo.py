"""Read and write helpers over the db tables. No business logic here."""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AnalysisRow, CodeSet, NoteRow
from app.models import AnalysisResult, Note, NoteCreate, Sentence


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
