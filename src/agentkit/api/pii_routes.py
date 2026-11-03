"""Redact text over HTTP. The placeholder map never leaves the process."""
from __future__ import annotations
from fastapi import APIRouter
from pydantic import BaseModel
from agentkit.pii import get_redactor

router = APIRouter(prefix='/api/pii', tags=['pii'])

class RedactIn(BaseModel):
    text: str


@router.post('/redact')
def redact(payload: RedactIn) -> dict:
    result = get_redactor().redact(payload.text)

    return {'redacted': result.text, 'count': result.count, 'kinds': [s.kind for s in result.spans]}