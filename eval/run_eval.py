"""Run the eval against the real LLM and code tables (local only; needs backend/.env).

Usage:
  python eval/run_eval.py --setup pipeline --limit 10 [--model M] [--run-id ID] [--interval 4]
Reruns with the same run id skip notes already completed, so a failed run resumes.
"""

import argparse
import logging
import os
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy.orm import Session

from app.api.deps import get_llm
from app.config import get_settings
from app.db.session import get_engine
from app.models.eval import GoldNote
from app.pipeline.state import PROMPT_VERSION
from app.terminology.embedder import get_embedder
from eval.gold import load_gold
from eval.records import NoteRun
from eval.report import RUNS, markdown, score_run, write_report
from eval.runner import DEFAULT_CALL_INTERVAL_S, PacedLlm, run_notes
from eval.setups import (
    BASELINE_PROMPT_VERSION,
    predict_baseline,
    predict_pipeline,
)


def main(default_setup: str | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--setup", choices=["pipeline", "baseline"], default=default_setup)
    parser.add_argument("--limit", type=int, default=None, help="first N gold notes")
    parser.add_argument("--model", help="overrides LLM_MODEL for this run only")
    parser.add_argument("--run-id", help="default: <date>-<setup>-<model>")
    parser.add_argument("--interval", type=float, default=DEFAULT_CALL_INTERVAL_S)
    args = parser.parse_args()
    if args.setup is None:
        parser.error("--setup is required")
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)

    if args.model:
        os.environ["LLM_MODEL"] = args.model
        get_settings.cache_clear()
    llm = PacedLlm(get_llm(), args.interval)
    model_slug = llm.model.replace("/", "_")
    run_id = args.run_id or f"{date.today().isoformat()}-{args.setup}-{model_slug}"
    run_dir = RUNS / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    version = PROMPT_VERSION if args.setup == "pipeline" else BASELINE_PROMPT_VERSION
    (run_dir / "meta.json").write_text(
        f'{{"run_id": "{run_id}", "setup": "{args.setup}", "model": "{llm.model}", '
        f'"prompt_version": "{version}"}}\n'
    )

    golds = load_gold()[: args.limit] if args.limit else load_gold()
    engine = get_engine()
    embedder = get_embedder() if args.setup == "pipeline" else None

    def predict(gold: GoldNote) -> NoteRun:
        with Session(engine) as session:
            if embedder is not None:
                return predict_pipeline(session, llm, embedder, gold)
            return predict_baseline(session, llm, gold)

    run_notes(golds, predict, run_dir)
    write_report(run_dir)
    meta, summary = score_run(run_dir, args.limit)
    print(markdown(meta, summary))


if __name__ == "__main__":
    main()
