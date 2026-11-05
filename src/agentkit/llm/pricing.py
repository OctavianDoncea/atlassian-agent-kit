"""USD cost of a Groq completion. Rates are read from Groq's published docs (the models table and the prompt-caching page) and kept in memory until
 ``llm_pricing_ttl_seconds`` elapses. This module does not contain a price list.
 """
from __future__ import annotations
import re
import threading
import time
import httpx
from collections.abc import Mapping
from dataclasses import dataclass
from agentkit.errors import PricingError

_PER_MILLION = 1_000_000
_MODEL_ROW = re.compile(r'^\|.*\]\(/docs/model/(?P<id>[^)]+)\)[^|]*\|\s*[^|]*\|\s*(?P<price>[^|]*)\|', re.MULTILINE)
_TOKEN_PRICE = re.compile(r'\$(\d+(?:\.\d+)?)\s*input\s*\$\s*(\d+(?:\.\d+)?)\s*output', re.IGNORECASE)
_CACHE_MODEL = re.compile(r'^\|\s*([a-z0-9][a-z0-9_./-]*)\s*\|', re.MULTILINE)
_CACHE_DISCOUNT = re.compile(r'(\d+(?:\.\d+)?)\s*%\s*discount\s+for\s+cached\s+input', re.IGNORECASE)
_HEADING = re.compile(r'^## ', re.MULTILINE)

_lock = threading.Lock()
_cached: tuple[float, dict[str, TokenRate]] | None = None

@dataclass(frozen=True)
class TokenRate:
    """USD per 1M tokens. ``cached_input`` falls back to ``input`` when Groq does not discount that model."""

    input: float
    output: float
    cached_input: float | None = None

    def cached_input_rate(self) -> float:
        return self.input if self.cached_input is None else self.cached_input


def clear_rate_cache() -> None:
    global _cached
    with _lock:
        _cached = None

def load_rates(*, refresh: bool = False) -> dict[str, TokenRate]:
    """Return Groq's current USD-per-1M table, reusing the last fetch inside the TTL."""
    global _cached
    from agentkit.config import get_settings

    settings = get_settings()
    base = settings.llm_base_url.lower()
    if base and 'groq.com' not in base:
        raise PricingError(f'Live token pricing is implemented for Groq. LLM_BASE_URL is {settings.llm_base_url!r}.')

    with _lock:
        now = time.monotonic()
        if not refresh and _cached is not None and _cached[0] > now:
            return _cached[1]
        rates = fetch_groq_rates(models_url=settings.groq_models_doc_url, caching_url=settings.groq_prompt_caching_doc_url)
        _cached = (now + settings.llm_pricing_ttl_seconds, rates)
        return rates

def fetch_groq_rates(*, client: httpx.Client | None = None, models_url: str, caching_url: str) -> dict[str, TokenRate]:
    if client is None:
        with httpx.Client(timeout=20, follow_redirects=True) as owned:
            return _fetch_groq_rates(owned, models_url, caching_url)
    return _fetch_groq_rates(client, models_url, caching_url)

def parse_groq_models(markdown: str) -> dict[str, TokenRate]:
    """Token rates from the models doc. Audio and per-character prices are skipped."""
    rates: dict[str, TokenRate] = {}
    for match in _MODEL_ROW.finditer(markdown):
        price = _TOKEN_PRICE.search(match.group('price'))
        if price is None:
            continue
        model_id = match.group('id').strip()
        rates[model_id] = TokenRate(input=float(price.group(1)), output=float(price.group(2)))
    if not rates:
        raise PricingError('Groq models doc did not contain any input/output token prices.')
    return rates

def apply_groq_cache_pricing(rates: dict[str, TokenRate], caching_markdown: str) -> dict[str, TokenRate]:
    section = _section(caching_markdown, 'Supported Models')
    models = set(_CACHE_MODEL.findall(section))
    discount = _CACHE_DISCOUNT.search(_section(caching_markdown, 'Pricing') or caching_markdown)

    if not models or discount is None:
        raise PricingError('Groq prompt-caching doc did not list cached models and a cached-input discount.')
    
    fraction = float(discount.group(1)) / 100
    if not 0 <= fraction <= 1:
        raise PricingError(f'Groq cached-input discount {discount.group(1)}% is outside 0-100.')
    
    updated: dict[str, TokenRate] = {}
    for model_id, rate in rates.items():
        cached = rate.input * (1 - fraction) if model_id in models else None
        updated[model_id] = TokenRate(input=rate.input, output=rate.output, cached_input=cached)
    
    return updated

def get_rate(model: str, rates: Mapping[str, TokenRate] | None = None) -> TokenRate:
    table = load_rates() if rates is None else rates
    rate = table.get(model.strip())
    if rate is None:
        known = ', '.join(sorted(table)) or 'none'
        raise PricingError(f'Groq docs have no USD-per-1M token price for {model.strip()!r}. Priced models: {known}.')
    return rate

def cost_usd(model: str, input_tokens: int, output_tokens: int, *, cached_input_tokens: int = 0, rates: Mapping[str, TokenRate] | None = None) -> float:
    """USD for one completion. ``cached_input_tokens`` is the cached subset of ``input_tokens``."""
    if input_tokens < 0 or output_tokens < 0 or cached_input_tokens < 0:
        raise PricingError('Token counts must be zero or positive.')
    
    if cached_input_tokens > input_tokens:
        raise PricingError('cached_input_tokens cannot exceed input_tokens.')
    
    rate = get_rate(model, rates)
    uncached = input_tokens - cached_input_tokens
    usd = uncached * rate.input + cached_input_tokens * rate.cached_input_rate() + output_tokens * rate.output
    
    return usd / _PER_MILLION

def _fetch_groq_rates(client: httpx.Client, models_url: str, caching_url: str) -> dict[str, TokenRate]:
    models = parse_groq_models(_read(client, models_url))
    return apply_groq_cache_pricing(models, _read(client, caching_url))

def _read(client: httpx.Client, url: str) -> str:
    try:
        response = client.get(url)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise PricingError(f'Could not read Groq pricing from {url}.') from exc
    return response.text

def _section(markdown: str, title: str) -> str:
    match = re.search(rf'^## \[{re.escape(title)}\]', markdown, re.MULTILINE)
    if match is None:
        return ''
    rest = markdown[match.end():]
    nxt = _HEADING.search(rest)
    return rest[: nxt.start()] if nxt else rest
