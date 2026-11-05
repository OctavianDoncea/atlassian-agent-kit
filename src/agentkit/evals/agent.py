from __future__ import annotations
import json
import logging
from typing import Any
from pydantic import BaseModel, ConfigDict, Field
from agentkit.config import get_settings
from agentkit.errors import AgentKitError
from agentkit.llm import chat_completion
from agentkit.llm.usage import UsageRecord
from agentkit.pii import RedactionResult, get_redactor

logger = logging.getLogger(__name__)

class AgentResponse(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    tool_name: str | None = None
    arguments: dict = Field(default_factory=dict)
    raw_content: str | None = None
    redaction: RedactionResult | None = None
    usage: UsageRecord | None = None


def build_tool_schemas(description_overrides: dict[str, None] | None = None, use_db: bool = True) -> list[dict]:
    """OpenAI tool schemas from the plugin registry."""
    from agentkit.plugins import get_registry

    active: dict[str, str] = {}

    if use_db:
        try:
            from agentkit.db.models import ToolSchema
            from agentkit.db.session import SessionLocal

            with SessionLocal() as db:
                for row in db.query(ToolSchema).filter_by(is_active=True).all():
                    active[row.tool_name] = row.description
        except Exception:
            active = {}

    return get_registry().openai_tools(overrides=description_overrides, active_descriptions=active)

def invoke_agent(prompt: str, model: str | None = None, temperature: float = 0.0, tools: list[dict] | None = None, llm_client: Any = None, redact: bool | None = None, ref: str | None = None) -> AgentResponse:
    settings = get_settings()
    if llm_client is None and not settings.groq_api_key:
        raise AgentKitError("GROQ_API_KEY is not set.")

    redactor = get_redactor()
    do_redact = redactor.enabled if redact is None else redact
    outbound = redactor.redact(prompt) if do_redact else RedactionResult(text=prompt)

    model = model or settings.llm_model
    tools = tools if tools is not None else build_tool_schemas()

    try:
        result = chat_completion(
            messages=[{'role': 'user', 'content': outbound.text}],
            purpose='agent',
            model=model,
            tools=tools,
            temperature=temperature,
            ref=ref,
            client=llm_client,
        )
    except Exception as exc:
        logger.error('LLM API call failed: %s', exc)
        return AgentResponse(raw_content=f'API Error: {exc}', redaction=outbound if outbound.spans else None)

    message = result.message
    shown = outbound if outbound.spans else None

    if message.tool_calls:
        tc = message.tool_calls[0]
        try:
            args = json.loads(tc.function.arguments)
        except json.JSONDecodeError:
            args = {'_raw_args': tc.function.arguments}
        return AgentResponse(tool_name=tc.function.name, arguments=args, raw_content=message.content, redaction=shown, usage=result.usage)

    return AgentResponse(raw_content=message.content or '', redaction=shown, usage=result.usage)