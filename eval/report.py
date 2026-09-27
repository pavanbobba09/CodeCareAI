"""Score run directories and write eval/results/<run_id>.json and .md."""

import json
from pathlib import Path
from typing import Any

from eval.gold import load_gold
from eval.metrics import THRESHOLDS, Summary, judge, summarize
from eval.runner import load_runs

RESULTS = Path(__file__).resolve().parent / "results"
RUNS = RESULTS / "runs"
METRICS = [
    "precision",
    "recall",
    "invented_rate",
    "invalid_rate",
    "evidence_ref_invalid_rate",
    "unsupported_rate",
    "gap_recall",
    "em_match",
]


def score_run(run_dir: Path, limit: int | None = None) -> tuple[dict[str, Any], Summary]:
    """Score a run over its own gold scope (meta "gold"), so a missing note is visible.

    Runs saved before scopes were recorded fall back to the first `limit` (or all) notes.
    """
    meta: dict[str, Any] = json.loads((run_dir / "meta.json").read_text())
    golds = load_gold()
    if "gold" in meta:
        golds = [g for g in golds if g.note_id in meta["gold"]]
    if limit:
        golds = golds[:limit]
    return meta, summarize(golds, load_runs(run_dir))


def _fmt(v: float | None) -> str:
    return "n/a" if v is None else f"{v:.2f}"


def coverage_line(s: Summary) -> str | None:
    if s.complete:
        return None
    parts = []
    if s.missing_notes:
        parts.append(f"{len(s.missing_notes)} missing ({', '.join(s.missing_notes)})")
    if s.failed_notes:
        parts.append(f"{s.failed_notes} failed")
    return f"**INCOMPLETE**: {'; '.join(parts)}. No metric is judged pass or fail."


def markdown(meta: dict[str, Any], s: Summary) -> str:
    incomplete = coverage_line(s)
    lines = [f"# Eval {meta['run_id']}", ""]
    if incomplete:
        lines += [incomplete, ""]
    lines += [
        f"Setup `{meta['setup']}`, model `{meta['model']}`, prompts `{meta['prompt_version']}`.",
        f"{s.notes} notes ({s.failed_notes} failed), {s.predicted_codes} predicted codes, "
        f"mean latency {s.mean_latency_ms} ms.",
        "",
        "| Metric | Value | Threshold |",
        "|---|---|---|",
    ]
    for m in METRICS:
        op, lim = THRESHOLDS[m]
        v = getattr(s, m)
        lines.append(f"| {m} | {_fmt(v)}{judge(m, v, s.complete)} | {op} {lim} |")
    lines += [
        "",
        "| Note | Status | Missed | Extra | Invented | Invalid | Unsupported "
        "| Gaps expected | Gaps raised |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for n in s.per_note:
        lines.append(
            f"| {n.note_id} | {n.status} | {', '.join(n.missed) or '-'} | "
            f"{', '.join(n.extra) or '-'} | {', '.join(n.invented) or '-'} | "
            f"{', '.join(n.invalid) or '-'} | {', '.join(n.unsupported) or '-'} | "
            f"{', '.join(n.gaps_expected) or '-'} | {', '.join(n.gaps_raised) or '-'} |"
        )
    return "\n".join(lines) + "\n"


def write_report(run_dir: Path) -> Path:
    meta, summary = score_run(run_dir)
    RESULTS.mkdir(parents=True, exist_ok=True)
    out = RESULTS / f"{meta['run_id']}.json"
    out.write_text(json.dumps({"meta": meta, "summary": summary.model_dump()}, indent=2) + "\n")
    (RESULTS / f"{meta['run_id']}.md").write_text(markdown(meta, summary))
    return out
