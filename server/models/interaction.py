"""Typed model for a completed call record written to the interactions sheet."""
from dataclasses import dataclass, field


@dataclass
class InteractionEntry:
    timestamp: str
    caller_phone: str
    caller_name: str
    call_id: str
    summary: str
    sentiment: str
    outcome: str
    recording_url: str = field(default="")
    transcript_url: str = field(default="")
