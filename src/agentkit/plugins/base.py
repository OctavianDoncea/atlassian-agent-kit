from __future__ import annotations
import httpx
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from pydantic import BaseModel
from agentkit.config import Settings
from agentkit.sdk.auth import AuthManager
from agentkit.sdk.token import TokenStoreProtocol

@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    model: type[BaseModel]
    invoke: Callable[[Any, BaseModel], Any]


class IntegrationPlugin(ABC):
    """Base class for all integrations, built-in or third-party."""
    name: str = ''
    display_name: str = ''
    version: str = '0.0.0'
    product: str | None = None

    @abstractmethod
    def tools(self) -> list[ToolSpec]:
        """Declare every tool this plugin exposes to agents."""

    def create_client(
        self,
        *,
        auth_mode: str = 'oauth',
        cloud_id: str | None = None,
        transport: httpx.BaseTransport | None = None,
        settings: Settings | None = None,
        use_async: bool = False,
        concurrency: int = 8,
        token_store: TokenStoreProtocol | None = None,
        auth_manager: AuthManager | None = None
    ) -> Any:
        """Build the object handlers receive as `client`."""
        return self

    def validate(self) -> None:
        """Optional startup hook for plugin-specific checks."""