"""A tiny OpenAI-compatible server that replays the recorded worked-example LLM responses.

Local end-to-end tests only (M8). The backend reaches it through LLM_BASE_URL alone, so the
app has no fake code path (CLAUDE.md rule 10). It answers POST .../chat/completions:
- the worked example gets its recorded extract and select responses;
- the e2e note (E2E_NOTE) gets hand-written responses in which the two codes cite
  different sentences, so an evidence-highlight test can tell them apart;
- any other note gets HTTP 503, which the UI shows as a failed analysis.

Usage: python scripts/fake_llm.py [--port 8765]
Then point the backend at it: LLM_BASE_URL=http://127.0.0.1:8765/v1 LLM_API_KEY=fake
LLM_MODEL=fake-replay.
"""

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
RECORDING = REPO / "backend" / "tests" / "fixtures" / "llm" / "worked_example"
WORKED = json.loads((REPO / "data" / "examples" / "worked_example.json").read_text())
FIRST_SENTENCE = WORKED["note"]["text"].split("\n")[0].removeprefix("Assessment: ")

# Synthetic. Sentence 1 supports E11.22, sentence 2 supports N18.32.
E2E_NOTE = (
    "Assessment: Type 2 diabetes mellitus with chronic kidney disease.\n"
    "Chronic kidney disease stage 3b per recent labs.\n"
    "Plan: Recheck renal function in 3 months.\n"
)
E2E_MARKER = "Chronic kidney disease stage 3b per recent labs."
_MDM = {"problems": None, "data": None, "risk": None, "evidence": []}
E2E_EXTRACT = {
    "facts": [
        {"fact_id": "f1", "kind": "condition",
         "concept": "type 2 diabetes mellitus with chronic kidney disease",
         "status": "active", "details": {"type": "2"}, "links": [], "evidence": [1]},
        {"fact_id": "f2", "kind": "condition", "concept": "chronic kidney disease",
         "status": "active", "details": {"stage": "3b"}, "links": [], "evidence": [2]},
    ],
    "mdm": _MDM,
}  # fmt: skip
E2E_SELECT = {
    "selections": [
        {"fact_id": "f1", "code": "E11.22", "evidence": [1], "rationale": "diabetes with CKD"},
        {"fact_id": "f2", "code": "N18.32", "evidence": [2], "rationale": "stage 3b"},
    ]
}


def _recorded(step: str) -> dict[str, object]:
    response: dict[str, object] = json.loads((RECORDING / f"{step}.json").read_text())["response"]
    return response


def reply_for(body: dict[str, object]) -> tuple[int, dict[str, object]]:
    """(status, JSON body) for one chat-completions request."""
    messages = body.get("messages")
    if not isinstance(messages, list) or len(messages) < 2:
        return 400, {"error": {"message": "expected system and user messages"}}
    system, user = str(messages[0].get("content", "")), str(messages[1].get("content", ""))
    if "extract clinical facts" in system:
        if E2E_MARKER in user:
            content = E2E_EXTRACT
        elif FIRST_SENTENCE in user:
            content = _recorded("extract")
        else:
            return 503, {"error": {"message": "fake LLM only knows its two notes"}}
    else:
        content = E2E_SELECT if '"3b"' in user else _recorded("select")
    return 200, {
        "choices": [{"message": {"role": "assistant", "content": json.dumps(content)}}],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0},
    }


class Handler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:
        if not self.path.endswith("/chat/completions"):
            self._send(404, {"error": {"message": "not found"}})
            return
        length = int(self.headers.get("Content-Length", "0"))
        status, body = reply_for(json.loads(self.rfile.read(length) or b"{}"))
        self._send(status, body)

    def _send(self, status: int, body: dict[str, object]) -> None:
        data = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Retry-After", "0")  # the client's one retry should not wait
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, fmt: str, *args: object) -> None:
        print(f"fake_llm: {fmt % args}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"fake_llm: serving the worked example on http://127.0.0.1:{args.port}/v1")
    server.serve_forever()


if __name__ == "__main__":
    main()
