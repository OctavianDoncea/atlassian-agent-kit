"""Central LLM gateway: one place every model call is made, measured, and priced."""
from __future__ import annotations
import logging
import time
from dataclasses import dataclass
from typing import Any
from openai import OpenAI
from agentkit.config import get_settings
from agentkit.errors import PricingError
from agentkit.llm.pricing import cost_usd
from agentkit.llm.tokens import estimate_message_tokens, estimate_messages_tokens, estimate_tools_tokens
from agentkit.llm.usage import UsageRecord, persist_usage

logger = logging.getLogger(__name__)

@dataclass
class LLMCallResult:
    message: Any
    response: Any
    usage: UsageRecord


def chat_completion(messages: list[dict], purpose: str, model: str | None = None, tools: list[dict] | None = None, temperature: float = 0.0, ref: str | None = None, client: Any = None,  response_format: dict | None = None,) -> LLMCallResult:
    settings = get_settings()
    model = model or settings.llm_model
    client = client or OpenAI(api_key=settings.groq_api_key, base_url=settings.llm_base_url or None)
    kwargs: dict[str, Any] = {'model': model, 'messages': messages, 'temperature': temperature}
    
    if tools is not None:
        kwargs['tools'] = tools
        kwargs['tool_choice'] = 'auto'
    
    if response_format:
        kwargs['response_format'] = response_format

    started = time.perf_counter()
    response = client.chat.completions.create(**kwargs)
    duration_ms = int((time.perf_counter() - started) * 1000)
    message = response.choices[0].message

    usage_obj = getattr(response, 'usage', None)
    cached = 0
    if usage_obj is not None and _count(usage_obj, 'prompt_tokens') is not None:
        in_tokens = _count(usage_obj, 'prompt_tokens') or 0
        out_tokens = _count(usage_obj, 'completion_tokens') or 0
        cached = _cached_tokens(usage_obj)
        estimated = False
    else:
        in_tokens = estimate_messages_tokens(messages) + estimate_tools_tokens(tools)
        out_tokens = estimate_message_tokens(message)
        estimated = True

    try:
        price = cost_usd(model, in_tokens, out_tokens, cached_input_tokens=cached)
    except PricingError as exc:
        logger.warning('token price unavailable, recording cost 0: %s', exc)
        price = 0.0

    record = UsageRecord(
        purpose=purpose,
        model=model,
        input_tokens=in_tokens,
        output_tokens=out_tokens,
        cost_usd=price,
        duration_ms=duration_ms,
        ref=ref,
        estimated=estimated,
    )
    persist_usage(record)
    return LLMCallResult(message=message, response=response, usage=record)

def _count(usage_obj: Any, name: str) -> int | None:
    value = usage_obj.get(name) if isinstance(usage_obj, dict) else getattr(usage_obj, name, None)
    return None if value is None else int(value)

def _cached_tokens(usage_obj: Any) -> int:
    details = usage_obj.get('prompt_tokens_details') if isinstance(usage_obj, dict) else getattr(usage_obj, 'prompt_tokens_details', None)
    
    if details is None:
        return 0
    
    if isinstance(details, dict):
        return int(details.get('cached_tokens') or 0)
    
    return int(getattr(details, 'cached_tokens', 0) or 0)