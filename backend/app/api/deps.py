"""Request-scoped services. Tests override these with recorded LLM responses."""

from app.config import get_settings
from app.llm.client import JsonLlm, LlmClient
from app.terminology.embedder import Embedder
from app.terminology.embedder import get_embedder as _get_embedder


def get_llm() -> JsonLlm:
    s = get_settings()
    return LlmClient(s.llm_base_url, s.llm_api_key, s.llm_model)


def get_embedder() -> Embedder:
    return _get_embedder()
