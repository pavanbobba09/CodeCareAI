"""Pipeline nodes, one file each. A node returns a dict of PipelineState updates."""

from typing import Any, Protocol

from app.pipeline.state import PipelineState


class Node(Protocol):
    # The parameter must be named `state` to match LangGraph's node protocol.
    def __call__(self, state: PipelineState) -> dict[str, Any]: ...
