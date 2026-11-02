"""PII/secret pattern catalogue. Each pattern carries a validator: we mask what we can PROVE is sensitive."""
from __future__ import annotations
import re
from collections.abc import Callable
from dataclasses import dataclass

@dataclass(frozen=True)
class PatternDef:
    kind: str
    regex: re.Pattern[str]
    validator: Callable[[str], bool] | None = None


# Validators
def luhn_ok(digits: str) -> bool:
    total = 0

    for i, d in enumerate(reversed([int(c) for c in digits])):
        if i % 2 == 0:
            d *= 2
            if d > 9:
                d -= 9
            
        total += d

    return total % 10 == 0

def iban_ok(value: str) -> bool:
    compact = re.sub(r'\s', '', value).upper()
    rearranged = compact[4:] + compact[:4]

    try:
        nums = ''.join(str(int(c, 36)) for c in rearranged)
    except ValueError:
        return False

    return int(nums) % 97 == 1

def ssn_ok(value: str) -> bool:
    parts = value.split('-')

    if len(parts) != 3:
        return False
    area, group, serial = parts
    if len(area) != 3 or len(group) != 2 or len(serial) != 4:
        return False
    if area in ('000', '666') or area.startswith('9'):
        return False
    if group == '00' or serial == '0000':
        return False


    return True

def digits_in(value: str, lo: int, hi: int) -> bool:
    return lo <= len(re.sub(r'\D', '', value)) <= hi

def not_iso_date(value: str) -> bool:
    return re.fullmatch(r'\d{4}[-/.]\d{1,2}[-/.]\d{1,2}', value.strip()) is None

PHONE_OK = lambda v: not_iso_date(v) and digits_in(v, 8, 15)
CC_OK = lambda v: digits_in(v, 13, 19) and luhn_ok(re.sub(r'\D', '', v))

# Catalogue
PATTERNS: list[PatternDef] = [
    PatternDef(
        'PRIVATE_KEY',
        re.compile(r'-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z0-9 ]*PRIVATE KEY-----'),
    ),
    PatternDef(
        'JWT',
        re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b"),
    ),
    
    PatternDef(
        'API_KEY',
        re.compile(r'\b(?:sk|pk|key|token|secret|pwd|pass)[-_]?[a-zA-Z0-9]{20,}\b'),
    ),
    PatternDef(
        'SECRET_ASSIGNMENT',
        re.compile(r"(?i)(?:api[_-]?key|secret[_-]?key|password|token|auth|credential)\s*[=:]?\s*['\"]([a-zA-Z0-9_\-]{16,})['\"]"),
    ),
    PatternDef('EMAIL', re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b')),
    PatternDef('IBAN', re.compile(r'\b[A-Z]{2}\d{2}[A-Z0-9]{11,30}\b'), iban_ok),
    PatternDef('IBAN', re.compile(r'\b[A-Z]{2}\d{2}(?:\s[A-Z0-9]{4}){2,7}(?:\s[A-Z0-9]{1,4})?\b'), iban_ok),
    PatternDef('CREDIT_CARD', re.compile(r'\b(?:\d[ -]?){12,18}\d\b'), CC_OK),
    PatternDef('NATIONAL_ID', re.compile(r'\b\d{3}-\d{2}-\d{4}\b'), ssn_ok),
    PatternDef('PHONE', re.compile(r'\+?\d(?:[\s().-]?\d){7,17}\b'), PHONE_OK),
    PatternDef('PRIVATE_IP', re.compile(r'\b(?:10\.\d{1,3}\.\d{1,3}\.\d{1,3}|172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}|192\.168\.\d{1,3}\.\d{1,3})\b'),),
    PatternDef('CREDENTIAL_URL', re.compile(r'\b[a-zA-Z][a-zA-Z0-9+.-]*:\/\/[^\s\/:]+:[^\s@]+@[^\s]+\b'),),
]

def classify_pii(text: str) -> list[str]:
    return [p.kind for p in PATTERNS if p.regex.search(text)]