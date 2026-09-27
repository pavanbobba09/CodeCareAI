"""Score run directories and write eval/results/<run_id>.json and .md."""

import json
from pathlib import Path

from eval.gold import load_gold
from eval.metrics import THRESHOLDS, Summary, meets, summarize
from eval.runner import load_runs

RESULTS = Path(__file__).resolve().parent / "results"
RUNS = RESULTS / "runs"
METRICS = [
    "precision",
    "recall",
    "invented_rate",
    "invalid_rate",
    "unsupported_rate",
    "gap_recall",
    "em_match",
]


def score_run(run_dir: Path, limit: int | None = None) -> tuple[dict[str, str], Summary]:
    meta: dict[str, str] = json.loads((run_dir / "meta.json").read_text())
    golds = load_gold()[:limit] if limit else load_gold()
    return meta, summarize(golds, load_runs(run_dir))


def _fmt(v: float | None) -> str:
    return "n/a" if v is None else f"{v:.2f}"


def _mark(metric: str, v: float | None) -> str:
    ok = meets(metric, v)
    return "" if ok is None else (" ✓" if ok else " ✗")


def markdown(meta: dict[str, str], s: Summary) -> str:
    lines = [
        f"# Eval {meta['run_id']}",
        "",
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
        lines.append(f"| {m} | {_fmt(v)}{_mark(m, v)} | {op} {lim} |")
    lines += [
        "",
        "| Note | Status | Missed | Extra | Invented | Invalid | Gaps expected | Gaps raised |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for n in s.per_note:
        lines.append(
            f"| {n.note_id} | {n.status} | {', '.join(n.missed) or '-'} | "
            f"{', '.join(n.extra) or '-'} | {', '.join(n.invented) or '-'} | "
            f"{', '.join(n.invalid) or '-'} | "
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
