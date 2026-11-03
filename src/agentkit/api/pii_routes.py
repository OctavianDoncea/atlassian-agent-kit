"""Try the redactor endpoints. Demo only."""
from __future__ import annotations
from fastapi import APIRouter
from pydantic import BaseModel
from agentkit.pii import get_redactor

router = APIRouter(prefix='/api/pii', tags=['pii'])

class RedactIn(BaseModel):
    text: str


class RestoreIn(BaseModel):
    text: str
    mapping: dict[str, str]


@router.post('/redact')
def redact(payload: RedactIn) -> dict:
    result = get_redactor().redact(payload.text)

    return {'redacted': result.text, 'count': result.count, 'kinds': [s.kind for s in result.spans], 'mapping': result.mapping}

@router.post('/restore')
def restore(payload: RestoreIn) -> dict:
    out = payload.text

    for ph, original in payload.mapping.items():
        out = out.replace(ph, original)

    return {'restored': out}