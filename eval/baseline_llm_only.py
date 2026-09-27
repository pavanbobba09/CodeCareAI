"""LLM-only baseline: same model, codes straight from the note, no candidates, no rules.

Usage: python eval/baseline_llm_only.py --limit 10 [--model M] [--run-id ID]
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from eval.run_eval import main

if __name__ == "__main__":
    main(default_setup="baseline")
