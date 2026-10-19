from agentkit.db.models import ToolSchema, Integration
from agentkit.db.session import SessionLocal
from agentkit.integrations.confluence import CONFLUENCE_TOOL_MODELS
from agentkit.integrations.jira import JIRA_TOOL_MODELS
from agentkit.sdk.schema import openai_tool

def main() -> None:
    with SessionLocal() as db:
        jira_int = db.query(Integration).filter_by(name='jira').one()
        conf_int = db.query(Integration).filter_by(name='confluence').one()

        db.query(ToolSchema).filter_by(is_active=True).update({ToolSchema.is_active: False})

        for name, (model, desc) in JIRA_TOOL_MODELS.items():
            schema = openai_tool(name, model, desc)
            db.add(ToolSchema(
                integration_id=jira_int.id, tool_name=name, version=1, description_variant='baseline',
                description=desc, json_schema=schema, is_active=True
            ))

        for name, (model, desc) in CONFLUENCE_TOOL_MODELS.items():
            schema = openai_tool(name, desc, model)
            db.add(ToolSchema(
                integration_id=conf_int.id, tool_name=name, version=1,
                description_variant='baseline', description=desc, json_schema=schema, is_active=True
            ))

        db.commit()
        print('Seeded baseline tool schemas.')

if __name__ == '__main__':
    main()