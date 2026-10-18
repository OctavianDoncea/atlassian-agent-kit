from __future__ import annotations
import json
import logging
from openai import OpenAI
from pydantic import BaseModel, Field
from agentkit.config import get_settings
from agentkit.errors import AgentKitError

logger = logging.getLogger(__name__)

class AgentResponse(BaseModel):
    tool_name: str | None = None
    arguments: dict = Field(default_factory=dict)
    raw_content: str | None = None


def build_tool_schemas() -> list[dict]:
    from agentkit.integrations.confluence import CONFLUENCE_TOOL_MODELS
    from agentkit.integrations.jira import JIRA_TOOL_MODELS
    from agentkit.sdk.schema import openai_tool

    tools = []
    for name, (model, desc) in JIRA_TOOL_MODELS.items():
        tools.append(openai_tool(name, desc, model))
    for name, (model, desc) in CONFLUENCE_TOOL_MODELS.items():
        tools.append(openai_tool(name, desc, model))
    
    return tools

def invoke_agent(prompt: str, model: str | None = None) -> AgentResponse:
    settings = get_settings()
    if not settings.groq_api_key:
        raise AgentKitError("GROQ_API_KEY is not set")

    model = model or settings.llm_model
    client = OpenAI(api_key=settings.groq_api_key, base_url=settings.llm_base_url)
    tools = build_tool_schemas()

    try:
        response = client.chat.completions.create(
            model=model,
            mesages=[{'role': 'user', 'content': prompt}],
            tools=tools,
            tool_choice='auto',
            temperature=0.0
        )
    except Exception as e:
        logger.error('LLM API call failed: %s', e)
        return AgentResponse(raw_content=f'API Error: {e}')

    message = response.choices[0].message

    if message.tool_calls:
        tc = message.tool_calls[0]
        try:
            args = json.loads(tc.function.arguments)
        except json.JSONDecodeError:
            args = {'_raw_args': tc.function.arguments}
        
        return AgentResponse(tool_name=tc.function.name, arguments=args, raw_content=message.content)

    return AgentResponse(raw_content=message.content or '')