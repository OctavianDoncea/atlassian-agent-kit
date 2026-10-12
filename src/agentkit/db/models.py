from __future__ import annotations
import enum
import uuid
from datetime import datetime
from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Index, Integer, String, Text, UniqueConstraint, Uuid, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from agentkit.db.session import Base

class IntegrationType(str, enum.Enum):
    jira = 'jira'
    confluence = 'confluence'


class Integration(Base):
    __tablename__ = 'integrations'

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(120), unique=True, index=True, nullable=False)
    type: Mapped[IntegrationType] = mapped_column(Enum(IntegrationType, name='integration_type'), nullable=False)
    base_url: Mapped[str | None] = mapped_column(String(500))
    cloud_id: Mapped[str | None] = mapped_column(String(120))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    tools: Mapped[list[ToolSchema]] = relationship(back_populates='integration', cascade='all, delete-orphan')

    def __repr__(self) -> str:
        return f'<Integration {self.name} ({self.type.value})>'


class ToolSchema(Base):
    __tablename__ = 'tool_schemas'
    __table_args__ = (UniqueConstraint('integration_id', 'tool_name', 'version', name='uq_tool_schema'),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    integration_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('integrations.id', ondelete='CASCADE'), index=True, nullable=False)
    tool_name: Mapped[str] = mapped_column(String(200), nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    description_variant: Mapped[str | None] = mapped_column(String(60))
    description: Mapped[str] = mapped_column(Text, nullable=False)
    json_schema: Mapped[dict] = mapped_column(JSONB, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    integration: Mapped[Integration] = relationship(back_populates='tools')
    eval_runs: Mapped[list[EvalRun]] = relationship(back_populates='tool_schema', cascade='all, delete-orphan')


class EvalRun(Base):
    __tablename__ = 'eval_runs'
    __table_args__ = (Index('ix_eval_runs_schema_created', 'tool_schema_id', 'created_at'),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tool_schema_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('tool_schemas.id', ondelete='CASCADE'), nullable=False)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    expected_tool: Mapped[str] = mapped_column(String(200), nullable=False)
    expected_params: Mapped[dict | None] = mapped_column(JSONB)
    actual_tool: Mapped[str | None] = mapped_column(String(200))
    actual_params: Mapped[dict | None] = mapped_column(JSONB)
    passed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    judge_provider: Mapped[str | None] = mapped_column(String(120))
    judge_reasoning: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    tool_schema: Mapped[ToolSchema] = relationship(back_populates='eval_runs')


class OAuthToken(Base):
    __tablename__ = 'oauth_tokens'

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    cloud_id: Mapped[str] = mapped_column(String(120), unique=True, index=True, nullable=False)
    site_url: Mapped[str] = mapped_column(String(500), nullable=False)
    access_token: Mapped[str] = mapped_column(Text, nullable=False)
    refresh_token: Mapped[str] = mapped_column(Text, nullable=False)
    scope: Mapped[str | None] = mapped_column(Text)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    def __repr__(self) -> str:
        return f'<OAuthToken cloud={self.cloud_id} expires_at={self.expires_at}>'