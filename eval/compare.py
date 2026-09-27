"""Print scored runs side by side against the DESIGN.md §9 thresholds.

Usage: python eval/compare.py RUN_ID [RUN_ID ...] [--limit N]
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from eval.metrics import THRESHOLDS, meets
from eval.report import METRICS, RUNS, score_run


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_ids", nargs="+")
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    scored = [score_run(RUNS / r, args.limit) for r in args.run_ids]
    header = ["Metric", "Threshold"] + [f"{m['setup']} / {m['model']}" for m, _ in scored]
    print("| " + " | ".join(header) + " |")
    print("|" + "---|" * len(header))
    for metric in METRICS:
        op, lim = THRESHOLDS[metric]
        cells = []
        for _, s in scored:
            v = getattr(s, metric)
            ok = meets(metric, v)
            cells.append(
                "n/a" if v is None else f"{v:.2f}" + ("" if ok is None else (" ✓" if ok else " ✗"))
            )
        print(f"| {metric} | {op} {lim} | " + " | ".join(cells) + " |")
    rows = [
        ("notes (failed)", [f"{s.notes} ({s.failed_notes})" for _, s in scored]),
        ("predicted codes", [str(s.predicted_codes) for _, s in scored]),
        ("mean latency ms", [str(s.mean_latency_ms) for _, s in scored]),
    ]
    for name, cells in rows:
        print(f"| {name} | | " + " | ".join(cells) + " |")


if __name__ == "__main__":
    main()
