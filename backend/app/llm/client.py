"""Provider-neutral OpenAI-compatible JSON client (DESIGN.md §3.1 llm_client, §4.4).

Provider and model come only from LLM_BASE_URL / LLM_API_KEY / LLM_MODEL.
Every call: temperature 0, JSON mode, Pydantic validation, at most one retry.
"""

import json
import logging
import time
from collections.abc import Callable
from typing import Literal, Protocol, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

log = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

LlmErrorCode = Literal["LLM_UNAVAILABLE", "LLM_BAD_OUTPUT", "TIMEOUT"]
RETRY_AFTER_CAP_S = 20.0
PER_CALL_TIMEOUT_S = 60.0


class LlmError(Exception):
    def __init__(self, code: LlmErrorCode, message: str) -> None:
        super().__init__(message)
        self.code: LlmErrorCode = code
        self.message = message


class JsonLlm(Protocol):
    """What the pipeline needs from an LLM. `step` names the call for replay/recording."""

    @property
    def model(self) -> str: ...

    def complete_json(
        self, step: str, system: str, user: str, schema: type[T], deadline: float
    ) -> T: ...


class _Transient(Exception):
    def __init__(self, message: str, wait_s: float) -> None:
        super().__init__(message)
        self.wait_s = wait_s


class _BadOutput(Exception):
    def __init__(self, message: str, content: str) -> None:
        super().__init__(message)
        self.content = content


def _retry_after(response: httpx.Response) -> float:
    try:
        return min(float(response.headers.get("retry-after", "1")), RETRY_AFTER_CAP_S)
    except ValueError:
        return 1.0


class LlmClient:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        # Missing config is reported when a call is made, so the API can still answer
        # 404/409 first and a failed analysis is stored with LLM_UNAVAILABLE.
        self._configured = bool(base_url and api_key and model)
        self._model = model
        self._http = httpx.Client(
            base_url=base_url.rstrip("/") or "http://unconfigured.invalid",
            headers={"Authorization": f"Bearer {api_key}"},
            transport=transport,
        )
        self._sleep = sleep
        self._clock = clock

    @property
    def model(self) -> str:
        return self._model

    def _remaining(self, deadline: float) -> float:
        remaining = deadline - self._clock()
        if remaining <= 0:
            raise LlmError("TIMEOUT", "Analysis time limit reached.")
        return remaining

    def _post(self, messages: list[dict[str, str]], deadline: float) -> str:
        timeout = min(PER_CALL_TIMEOUT_S, self._remaining(deadline))
        try:
            response = self._http.post(
                "/chat/completions",
                json={
                    "model": self._model,
                    "temperature": 0,
                    "response_format": {"type": "json_object"},
                    "messages": messages,
                },
                timeout=timeout,
            )
        except httpx.TimeoutException as exc:
            raise _Transient("LLM request timed out.", 0.0) from exc
        except httpx.TransportError as exc:
            raise _Transient(f"LLM transport error: {type(exc).__name__}.", 1.0) from exc

        if response.status_code == 429 or response.status_code >= 500:
            raise _Transient(f"LLM HTTP {response.status_code}.", _retry_after(response))
        if response.status_code == 400 and "json_validate_failed" in response.text:
            # Provider-side JSON mode failure: treat like invalid output.
            raise _BadOutput("Provider could not produce valid JSON.", "")
        if response.status_code >= 400:
            raise LlmError("LLM_UNAVAILABLE", f"LLM HTTP {response.status_code}.")
        try:
            content = response.json()["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise LlmError("LLM_UNAVAILABLE", "LLM response had no message content.") from exc
        if not isinstance(content, str):
            raise LlmError("LLM_UNAVAILABLE", "LLM response had no message content.")
        return content

    @staticmethod
    def _parse(content: str, schema: type[T]) -> T:
        try:
            return schema.model_validate(json.loads(content))
        except (json.JSONDecodeError, ValidationError) as exc:
            raise _BadOutput(str(exc)[:1000], content) from exc

    def complete_json(
        self, step: str, system: str, user: str, schema: type[T], deadline: float
    ) -> T:
        if not self._configured:
            raise LlmError(
                "LLM_UNAVAILABLE", "LLM_BASE_URL, LLM_API_KEY and LLM_MODEL must be set."
            )
        messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
        retried = False
        while True:
            try:
                return self._parse(self._post(messages, deadline), schema)
            except _Transient as exc:
                if retried:
                    raise LlmError("LLM_UNAVAILABLE", str(exc)) from exc
                retried = True
                log.warning("llm %s: %s; retrying once", step, exc)
                self._sleep(min(exc.wait_s, self._remaining(deadline)))
            except _BadOutput as exc:
                if retried:
                    raise LlmError("LLM_BAD_OUTPUT", f"Invalid model output: {exc}") from exc
                retried = True
                log.warning("llm %s: invalid output; retrying once with the error", step)
                if exc.content:
                    messages.append({"role": "assistant", "content": exc.content})
                messages.append(
                    {
                        "role": "user",
                        "content": "Your last reply was not valid JSON for the schema. "
                        f"Error: {exc}\nReply again with only the corrected JSON object.",
                    }
                )
