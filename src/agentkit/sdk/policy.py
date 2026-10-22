"""Shared resilience policy for sync and async HTTP clients."""

from __future__ import annotations
from typing import Mapping

MAX_RETRY_AFTER_SECONDS = 30.0

def retry_after_seconds(headers: Mapping[str, str], attempt: int, default: float = 1.0) -> float:
    raw = headers.get('Retry-After') or headers.get('retry-after')
    try:
        delay = float(raw) if raw else default * attempt
    except ValueError:
        delay = default * attempt
    
    return min(max(delay, 0.0), MAX_RETRY_AFTER_SECONDS)

def is_rate_limited(status: int) -> bool:
    return status == 429

def is_auth_failure(status: int) -> bool:
    return status == 401