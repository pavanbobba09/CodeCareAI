"""A tiny OpenAI-compatible server that replays the recorded worked-example LLM responses.

Local end-to-end tests only (M8). The backend reaches it through LLM_BASE_URL alone, so the
app has no fake code path (CLAUDE.md rule 10). It answers POST .../chat/completions:
- the extract call for the worked example gets the recorded extract response;
- the select call gets the recorded select response;
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
        if FIRST_SENTENCE not in user:
            return 503, {"error": {"message": "fake LLM only knows the worked example"}}
        content = _recorded("extract")
    else:
        content = _recorded("select")
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
