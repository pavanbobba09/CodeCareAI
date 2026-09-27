"""Eval metrics (DESIGN.md §9). Pure: works on saved NoteRuns, no db, no LLM.

Codes are compared as exact strings, micro-averaged over all notes.
A failed note counts as predicting nothing (it hurts recall, it is not skipped).
"""

from pydantic import BaseModel

from app.models.eval import GoldNote
from eval.records import NoteRun

# DESIGN.md §9 thresholds: (metric, comparison, value)
THRESHOLDS: dict[str, tuple[str, float]] = {
    "invented_rate": ("==", 0.0),
    "invalid_rate": ("==", 0.0),
    "unsupported_rate": ("<=", 0.05),
    "precision": (">=", 0.85),
    "recall": (">=", 0.80),
    "gap_recall": (">=", 0.80),
    "em_match": (">=", 0.75),
}


class NoteScore(BaseModel):
    note_id: str
    status: str
    expected: list[str]
    predicted: list[str]
    missed: list[str]
    extra: list[str]
    invented: list[str]
    invalid: list[str]
    unsupported: list[str]
    gaps_expected: list[str]
    gaps_raised: list[str]


class Summary(BaseModel):
    notes: int
    failed_notes: int
    predicted_codes: int
    precision: float | None
    recall: float | None
    invented_rate: float | None
    invalid_rate: float | None
    unsupported_rate: float | None
    gap_recall: float | None
    em_match: float | None  # None while no gold note has expected_em
    mean_latency_ms: int
    per_note: list[NoteScore]


def _ratio(num: int, den: int) -> float | None:
    return round(num / den, 4) if den else None


def score_note(gold: GoldNote, run: NoteRun) -> NoteScore:
    expected = {c.code for c in gold.expected_codes}
    predicted = {p.code for p in run.predicted}
    valid_sentences = set(range(1, run.n_sentences + 1))
    unsupported = {
        p.code
        for p in run.predicted
        if not p.evidence or any(n not in valid_sentences for n in p.evidence)
    }
    return NoteScore(
        note_id=gold.note_id,
        status=run.status,
        expected=sorted(expected),
        predicted=sorted(predicted),
        missed=sorted(expected - predicted),
        extra=sorted(predicted - expected),
        invented=sorted({p.code for p in run.predicted if not p.in_code_set}),
        invalid=sorted({p.code for p in run.predicted if not (p.in_code_set and p.billable)}),
        unsupported=sorted(unsupported),
        gaps_expected=sorted(gold.expected_gap_rules),
        gaps_raised=sorted(set(run.gap_rules)),
    )


def summarize(golds: list[GoldNote], runs: dict[str, NoteRun]) -> Summary:
    scores = [score_note(g, runs[g.note_id]) for g in golds if g.note_id in runs]
    tp = sum(len(set(s.expected) & set(s.predicted)) for s in scores)
    n_pred = sum(len(s.predicted) for s in scores)
    n_exp = sum(len(s.expected) for s in scores)
    gaps_exp = sum(len(s.gaps_expected) for s in scores)
    gaps_hit = sum(len(set(s.gaps_expected) & set(s.gaps_raised)) for s in scores)
    em_golds = [g for g in golds if g.expected_em is not None and g.note_id in runs]
    em_hits = sum(1 for g in em_golds if runs[g.note_id].em_code == g.expected_em)
    latencies = [runs[s.note_id].latency_ms for s in scores]
    return Summary(
        notes=len(scores),
        failed_notes=sum(1 for s in scores if s.status != "completed"),
        predicted_codes=n_pred,
        precision=_ratio(tp, n_pred),
        recall=_ratio(tp, n_exp),
        invented_rate=_ratio(sum(len(s.invented) for s in scores), n_pred),
        invalid_rate=_ratio(sum(len(s.invalid) for s in scores), n_pred),
        unsupported_rate=_ratio(sum(len(s.unsupported) for s in scores), n_pred),
        gap_recall=_ratio(gaps_hit, gaps_exp),
        em_match=_ratio(em_hits, len(em_golds)),
        mean_latency_ms=int(sum(latencies) / len(latencies)) if latencies else 0,
        per_note=scores,
    )


def meets(metric: str, value: float | None) -> bool | None:
    """True/False against the DESIGN threshold; None when the metric is not measured."""
    if value is None or metric not in THRESHOLDS:
        return None
    op, limit = THRESHOLDS[metric]
    return {"==": value == limit, "<=": value <= limit, ">=": value >= limit}[op]
