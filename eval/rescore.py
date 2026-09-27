"""CI gate: re-score every committed run; fail if a pipeline run has an invented or invalid code.

No db and no LLM needed: runs store whether each predicted code is in the code set for the
visit date and billable.
Usage: python eval/rescore.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from eval.metrics import Summary
from eval.report import RUNS, score_run

PIPELINE_GATES = ("invented_rate", "invalid_rate")


def pipeline_gate_failures(run_id: str, summary: Summary) -> list[str]:
    """CI failures for one pipeline run. Report-only metrics are intentionally absent."""
    failures = []
    if not summary.complete:
        failures.append(f"{run_id}: incomplete run")
    for metric in PIPELINE_GATES:
        value = getattr(summary, metric)
        if value is None:
            failures.append(f"{run_id}: {metric} is unmeasured")
        elif value > 0:
            codes = sorted(
                {
                    code
                    for note in summary.per_note
                    for code in getattr(
                        note, "invented" if metric == "invented_rate" else "invalid"
                    )
                }
            )
            failures.append(f"{run_id}: {metric} failed for codes {codes}")
    return failures


def main() -> None:
    failures = []
    run_dirs = (
        sorted(p for p in RUNS.iterdir() if (p / "meta.json").exists()) if RUNS.exists() else []
    )
    if not run_dirs:
        sys.exit("no committed eval runs found in eval/results/runs")
    for run_dir in run_dirs:
        meta, s = score_run(run_dir)
        print(
            f"{meta['run_id']}: notes={s.notes} failed={s.failed_notes} "
            f"precision={s.precision} recall={s.recall} invented_rate={s.invented_rate} "
            f"invalid_rate={s.invalid_rate}" + ("" if s.complete else " INCOMPLETE")
        )
        if meta["setup"] != "pipeline":
            continue
        failures += pipeline_gate_failures(meta["run_id"], s)
    if failures:
        sys.exit("pipeline code gate failed:\n" + "\n".join(failures))
    print("pipeline gates: pass")


if __name__ == "__main__":
    main()
