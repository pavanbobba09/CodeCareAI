"""CI gate: re-score every committed run; fail if a pipeline run has an invented or invalid code.

No db and no LLM needed: runs store whether each predicted code is in the code set for the
visit date and billable.
Usage: python eval/rescore.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from eval.report import RUNS, score_run


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
        if (s.invented_rate or 0) > 0:
            invented = sorted({c for n in s.per_note for c in n.invented})
            failures.append(f"{meta['run_id']}: invented codes {invented}")
        if (s.invalid_rate or 0) > 0:
            invalid = sorted({c for n in s.per_note for c in n.invalid})
            failures.append(f"{meta['run_id']}: invalid codes {invalid}")
    if failures:
        sys.exit("pipeline code gate failed:\n" + "\n".join(failures))
    print("invented-code and invalid-code gates: pass")


if __name__ == "__main__":
    main()
