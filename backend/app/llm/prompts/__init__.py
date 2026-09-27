"""Versioned prompt files. To change a prompt, add a new version; never edit an old one."""

import hashlib
import json
from pathlib import Path

from pydantic import BaseModel

PROMPT_DIR = Path(__file__).parent


def load_prompt(name: str, schema: type[BaseModel]) -> str:
    """Prompt text with the output JSON schema filled in at {{SCHEMA}}."""
    text = (PROMPT_DIR / f"{name}.md").read_text()
    return text.replace("{{SCHEMA}}", json.dumps(schema.model_json_schema(), indent=1))


def prompt_hash(system: str, user: str) -> str:
    return hashlib.sha256(f"{system}\n\x00\n{user}".encode()).hexdigest()
