from __future__ import annotations
import json
import logging
from openai import OpenAI
from pydantic import BaseModel, Field
from agentkit.config import get_settings
from agentkit.errors import AgentKitError
from agentkit.sdk.schema import openai_tool

logger = logging.getLogger(__name__)

class AgentResponse(BaseModel):
    tool_name: str | None = None
    arguments: dict = Field(default_factory=dict)
    raw_content: str | None = None


def build_tool_schemas(description_overrides: dict[str, None] | None = None, use_db: bool = True) -> list[dict]:
    from agentkit.integrations.confluence import CONFLUENCE_TOOL_MODELS
    from agentkit.integrations.jira import JIRA_TOOL_MODELS

    registry: dict[str, tuple[type, str]] = {**JIRA_TOOL_MODELS, **CONFLUENCE_TOOL_MODELS}
    active_desc: dict[str, str] = {}

    if use_db:
        try:
            from agentkit.db.models import ToolSchema
            from agentkit.db.session import SessionLocal

            with SessionLocal() as db:
                for row in db.query(ToolSchema).filter_by(is_active=True).all():
                    active_desc[row.tool_name] = row.description
        except Exception:
            active_desc = {}

    tools = []
    for name, (model, desc) in registry.items():
        final_desc = (description_overrides or {}).get(name) or active_desc.get(name) or desc
        tools.append(openai_tool(name, final_desc, model))
    
    return tools

def invoke_agent(prompt: str, model: str | None = None, temperature: float = 0.0, tools: list[dict] | None = None) -> AgentResponse:
    settings = get_settings()
    if not settings.groq_api_key:
        raise AgentKitError("GROQ_API_KEY is not set.")

    model = model or settings.llm_model
    client = OpenAI(api_key=settings.groq_api_key, base_url=settings.llm_base_url)
    tools = tools if tools is not None else build_tool_schemas()

    try:
        response = client.chat.completions.create(
            model = model,
            messages = [{"role": "user", "content": prompt}],
            tools = tools,
            tool_choice = "auto",
            temperature = temperature
        )
    except Exception as exc:
        logger.error('LLM API call failed: %s', exc)
        return AgentResponse(raw_content=f'API Error: {exc}')

    message = response.choices[0].message

    if message.tool_calls:
        tc = message.tool_calls[0]
        try:
            args = json.loads(tc.function.arguments)
        except json.JSONDecodeError:
            args = {'_raw_args': tc.function.arguments}
        
        return AgentResponse(tool_name=tc.function.name, arguments=args, raw_content=message.content)

    return AgentResponse(raw_content=message.content or '')