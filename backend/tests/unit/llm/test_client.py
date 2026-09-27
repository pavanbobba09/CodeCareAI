import json
from collections.abc import Callable

import httpx
import pytest
from pydantic import BaseModel

from app.llm.client import CallUsage, LlmClient, LlmError


class Out(BaseModel):
    answer: str


Handler = Callable[[httpx.Request], httpx.Response]


def _ok(content: str) -> httpx.Response:
    return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})


class Fake:
    """Scripted fake server: returns the next response, records requests and sleeps."""

    def __init__(self, *responses: httpx.Response | Exception) -> None:
        self.responses = list(responses)
        self.requests: list[dict[str, object]] = []
        self.sleeps: list[float] = []
        self.now = 0.0

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(json.loads(request.content))
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    def client(self) -> LlmClient:
        return LlmClient(
            "http://llm.test/v1",
            "test-key",
            "test-model",
            transport=httpx.MockTransport(self.handler),
            sleep=self.sleeps.append,
            clock=lambda: self.now,
        )


def _call(fake: Fake, deadline: float = 100.0) -> Out:
    return fake.client().complete_json("extract", "sys", "user json", Out, deadline)


def test_success_sends_json_mode_temperature_zero_and_model() -> None:
    fake = Fake(_ok('{"answer": "yes"}'))

    assert _call(fake) == Out(answer="yes")
    body = fake.requests[0]
    assert body["model"] == "test-model"
    assert body["temperature"] == 0
    assert body["response_format"] == {"type": "json_object"}


def test_invalid_json_retries_once_with_the_error() -> None:
    fake = Fake(_ok("not json"), _ok('{"answer": "fixed"}'))

    assert _call(fake) == Out(answer="fixed")
    retry_messages = fake.requests[1]["messages"]
    assert isinstance(retry_messages, list)
    assert retry_messages[-2] == {"role": "assistant", "content": "not json"}
    assert "not valid JSON" in retry_messages[-1]["content"]


def test_schema_failure_twice_is_bad_output() -> None:
    fake = Fake(_ok('{"wrong": 1}'), _ok('{"still": "wrong"}'))

    with pytest.raises(LlmError) as err:
        _call(fake)
    assert err.value.code == "LLM_BAD_OUTPUT"
    assert len(fake.requests) == 2


def test_provider_json_validate_failed_counts_as_bad_output() -> None:
    fake = Fake(
        httpx.Response(400, json={"error": {"code": "json_validate_failed"}}),
        _ok('{"answer": "ok"}'),
    )
    assert _call(fake) == Out(answer="ok")


def test_429_waits_retry_after_then_retries() -> None:
    fake = Fake(httpx.Response(429, headers={"retry-after": "7"}), _ok('{"answer": "ok"}'))

    assert _call(fake) == Out(answer="ok")
    assert fake.sleeps == [7.0]


def test_retry_after_is_capped_at_20_seconds() -> None:
    fake = Fake(httpx.Response(429, headers={"retry-after": "120"}), _ok('{"answer": "ok"}'))
    _call(fake)
    assert fake.sleeps == [20.0]


def test_retry_after_wait_never_passes_the_deadline() -> None:
    fake = Fake(httpx.Response(429, headers={"retry-after": "15"}), _ok('{"answer": "ok"}'))
    _call(fake, deadline=5.0)
    assert fake.sleeps == [5.0]


def test_two_server_errors_are_unavailable() -> None:
    fake = Fake(httpx.Response(503), httpx.Response(500))

    with pytest.raises(LlmError) as err:
        _call(fake)
    assert err.value.code == "LLM_UNAVAILABLE"
    assert len(fake.requests) == 2


def test_timeout_retries_immediately_then_unavailable() -> None:
    fake = Fake(httpx.ReadTimeout("slow"), httpx.ReadTimeout("slow"))

    with pytest.raises(LlmError) as err:
        _call(fake)
    assert err.value.code == "LLM_UNAVAILABLE"
    assert fake.sleeps == [0.0]


def test_only_one_retry_across_error_kinds() -> None:
    fake = Fake(httpx.Response(429), _ok("not json"))

    with pytest.raises(LlmError) as err:
        _call(fake)
    assert err.value.code == "LLM_BAD_OUTPUT"
    assert len(fake.requests) == 2


def test_auth_error_is_unavailable_without_retry() -> None:
    fake = Fake(httpx.Response(401, json={"error": "bad key"}))

    with pytest.raises(LlmError) as err:
        _call(fake)
    assert err.value.code == "LLM_UNAVAILABLE"
    assert len(fake.requests) == 1


def test_past_deadline_is_timeout_without_a_request() -> None:
    fake = Fake(_ok('{"answer": "never"}'))
    fake.now = 200.0

    with pytest.raises(LlmError) as err:
        _call(fake, deadline=100.0)
    assert err.value.code == "TIMEOUT"
    assert fake.requests == []


def test_missing_config_is_unavailable_at_call_time() -> None:
    client = LlmClient("", "key", "model")  # constructing must not raise
    with pytest.raises(LlmError) as err:
        client.complete_json("extract", "sys", "user", Out, deadline=100.0)
    assert err.value.code == "LLM_UNAVAILABLE"


def _with_usage(content: str, usage: dict[str, object]) -> httpx.Response:
    return httpx.Response(
        200, json={"choices": [{"message": {"content": content}}], "usage": usage}
    )


def _usage_client(fake: Fake, seen: list[CallUsage]) -> LlmClient:
    return LlmClient(
        "http://llm.test/v1",
        "test-key",
        "test-model",
        transport=httpx.MockTransport(fake.handler),
        sleep=fake.sleeps.append,
        clock=lambda: fake.now,
        on_usage=seen.append,
    )


def test_usage_is_reported_per_call_with_reasoning_when_given() -> None:
    usage = {
        "prompt_tokens": 1400,
        "completion_tokens": 350,
        "completion_tokens_details": {"reasoning_tokens": 120},
    }
    fake = Fake(_with_usage('{"answer": "x"}', usage))
    seen: list[CallUsage] = []

    _usage_client(fake, seen).complete_json("extract", "sys", "user", Out, 100.0)

    assert seen == [
        CallUsage(step="extract", prompt_tokens=1400, completion_tokens=350, reasoning_tokens=120)
    ]


def test_invalid_output_still_reports_the_tokens_it_spent() -> None:
    fake = Fake(
        _with_usage("not json", {"prompt_tokens": 10, "completion_tokens": 5}),
        _with_usage('{"answer": "x"}', {"prompt_tokens": 20, "completion_tokens": 6}),
    )
    seen: list[CallUsage] = []

    _usage_client(fake, seen).complete_json("select", "sys", "user", Out, 100.0)

    assert [(u.prompt_tokens, u.completion_tokens, u.reasoning_tokens) for u in seen] == [
        (10, 5, None),
        (20, 6, None),
    ]


def test_no_usage_block_reports_nothing() -> None:
    seen: list[CallUsage] = []
    _usage_client(Fake(_ok('{"answer": "x"}')), seen).complete_json("x", "s", "u", Out, 100.0)

    assert seen == []
