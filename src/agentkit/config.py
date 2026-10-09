from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore', case_sensitive=False)

    database_url: str = 'postgresql+psycopg://agentkit:agentkit@localhost:5432/agentkit'
    atlassian_client_id: str = ''
    atlassian_client_secret: str = ''
    atlassian_redirect_uri: str = 'http://localhost:8000/auth/atlassian/callback'
    atlassian_scopes: str = (
        'read:jira-work write:jira-work read:jira-user '
        'read:confluence-content.all write:confluence-content read:confluence-space.all '
        'offline_access'
    )
    atlassian_site_url: str = ''
    atlassian_email: str = ''
    atlassian_api_token: str = ''
    groq_api_key: str = ''
    llm_model: str = 'openai/gpt-oss-120b'
    app_env: str = 'dev'


@lru_cache()
def get_settings() -> Settings:
    return Settings()