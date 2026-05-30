"""Typed model for a single VAPI tool call result item."""
from dataclasses import dataclass
from typing import Any


@dataclass
class ToolCallResult:
    tool_call_id: str
    result: Any
