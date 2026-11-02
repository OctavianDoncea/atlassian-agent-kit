from __future__ import annotations
import logging
from dataclasses import dataclass
from typing import Protocol
from agentkit.pii.patterns import PATTERNS, PatternDef

logger = logging.getLogger(__name__)

@dataclass(frozen=True)
class Detection:
    kind: str
    start: int
    end: int
    value: str


class DetectionEngine(Protocol):
    name: str

    def detect(self, text: str) -> list[Detection]: ...


def resolve_overlaps(detections: list[Detection]) -> list[Detection]:
    ordered = sorted(detections, key=lambda d: (d.start, -(d.end - d.start)))
    out: list[Detection] = []
    last_end = -1

    for d in ordered:
        if d.start < last_end:
            continue

        out.append(d)
        last_end = d.end

    return out

class RegexEngine:
    name = 'regex'

    def __init__(self, patterns: list[PatternDef] | None = None):
        self._patterns = patterns or PATTERNS

    def detect(self, text: str) -> list[Detection]:
        raw: list[Detection] = []

        for pat in self._patterns:
            for m in pat.regex.finditer(text):
                value = m.group(0)

                if pat.validator is not None and not pat.validator(value):
                    continue

                raw.append(Detection(pat.kind, m.start(), m.end(), value))

        return resolve_overlaps(raw)


class PresidioEngine:
    """Optional NER layer. Constructing without presidio installed raises ImportError."""

    name = 'presidio'
    _MAP = {
        'EMAIL_ADDRESS': 'EMAIL',
        'PHONE_NUMBER': 'PHONE',
        'CREDIT_CARD': 'CREDIT_CARD',
        'IBAN_CODE': 'IBAN',
        'PERSON': 'PERSON'
    }

    def __init__(self) -> None:
        from presidio_analyzer import AnalyzerEngine

        self._analyzer = AnalyzerEngine()

    def detect(self, text: str) -> list[Detection]:
        out = [
            Detection(kind, r.start, r.end, text[r.start : r.end])
            for r in self._analyzer.analyze(text=text, language='en') if (kind := self._MAP.get(r.entity_type))
        ]

        return resolve_overlaps(out)


class CompositeEngine:
    name = 'composite'

    def __init__(self, *engines: DetectionEngine):
        self._engines = engines

    def detect(self, text: str) -> list[Detection]:
        merged: list[Detection] = []

        for engine in self._engines:
            merged.extend(engine.detect(text))

        return resolve_overlaps(merged)


def build_engine(use_presidio: bool) -> DetectionEngine:
    if use_presidio:
        try:
            return CompositeEngine(RegexEngine(), PresidioEngine())
        except Exception as exc:
            logger.warning(f'Presidio unavailable ({exc}); falling back to regex engine')

    return RegexEngine()