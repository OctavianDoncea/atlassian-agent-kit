from __future__ import annotations
import hashlib
from dataclasses import dataclass, field
from typing import Any
from agentkit.config import get_settings
from agentkit.pii.engine import DetectionEngine, build_engine

@dataclass(frozen=True)
class Span:
    kind: str
    start: int
    end: int
    value: str
    placeholder: str


@dataclass
class RedactionResult:
    text: str
    spans: list[Span] = field(default_factory=list)

    @property
    def count(self) -> int:
        return len(self.spans)

    def restore(self, text: str | None = None) -> str:
        out = self.text if text is None else text

        for span in self.spans:
            out = out.replace(span.placeholder, span.value)

        return out


def placeholder_for(kind: str, value: str) -> str:
    return f'[{kind}_{hashlib.sha256(value.encode()).hexdigest()[:8]}]'

class Redactor:
    def __init__(self, engine: DetectionEngine | None = None, enabled: bool | None = None):
        settings = get_settings()
        self._engine = engine or build_engine(settings.pii_use_presidio)
        self.enabled = settings.pii_enabled if enabled is None else enabled

    def redact(self, text: str) -> RedactionResult:
        if not self.enabled or not text:
            return RedactionResult(text=text or '')

        detections = self._engine.detect(text)

        if not detections:
            return RedactionResult(text=text)

        chunks: list[str] = []
        spans: list[Span] = []
        cursor = 0

        for d in detections:
            ph = placeholder_for(d.kind, d.value)
            chunks.append(text[cursor : d.start])
            chunks.append(ph)
            spans.append(Span(d.kind, d.start, d.end, d.value, ph))
            cursor = d.end
        chunks.append(text[cursor:])

        return RedactionResult(text=''.join(chunks), spans=spans)


def restore_any(obj: Any, mapping: dict[str, str]) -> Any:
    """Recursively re-identify placeholders inside tool call arguments."""
    if isinstance(obj, str):
        for ph, original in mapping.items():
            obj = obj.replace(ph, original)

        return obj

    if isinstance(obj, dict):
        return {k: restore_any(v, mapping) for k, v in obj.items()}

    if isinstance(obj, list):
        return [restore_any(v, mapping) for v in obj]

    return obj

_redactor: Redactor | None = None

def get_redactor(reload: bool = False) -> Redactor:
    global _redactor

    if _redactor is None or reload:
        _redactor = Redactor()

    return _redactor