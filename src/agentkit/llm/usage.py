"""Usage records and best effort persistence: metrics must never break the call they measure."""
from __future__ import annotations
import logging
from dataclasses import dataclass
from decimal import Decimal
from agentkit.db.models import LLMUsage
from agentkit.db.session import SessionLocal

logger = logging.getLogger(__name__)

@dataclass(frozen=True)
class UsageRecord:
    purpose: str
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    duration_ms: int
    ref: str | None = None
    estimated: bool = False

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

def persist_usage(record: UsageRecord) -> None:
    try:
        with SessionLocal() as db:
            db.add(LLMUsage(
                purpose=record.purpose,
                model=record.model,
                ref=record.ref,
                input_tokens=record.input_tokens,
                output_tokens=record.output_tokens,
                total_tokens=record.total_tokens,
                cost_usd=Decimal(str(round(record.cost_usd, 8))),
                estimated=record.estimated,
                duration_ms=record.duration_ms,
            ))
            db.commit()
    except Exception as exc:
        logger.warning('usage persistence failed (non-fatal): %s', exc)