from dataclasses import dataclass
from typing import Any


@dataclass
class ToolCallResult:
    tool_call_id: str
    result: Any
