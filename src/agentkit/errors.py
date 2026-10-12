from __future__ import annotations

class AgentKitError(Exception):
    """Base class for all SDK errors."""


class AuthError(AgentKitError):
    """OAuth configuration / token problems."""


class InvalidStateError(AuthError):
    """OAuth `state` parameter failed validation (possible CSRF)."""


class TokenRefreshError(AuthError):
    """Refresh-token exchange failed."""


class NotConnectedError(AuthError):
    """No stored OAuth tokens for the requested cloud id."""


class AtlassianAPIError(AgentKitError):
    def __init__(self, status_code: int, message: str, *, body: str | None = None, url: str | None = None):
        self.status_code = status_code
        self.body = body
        self.url = url
        super().__init__(f'[{status_code}] {message}' + (f' :: {body}' if body else ''))


class RateLimitError(AtlassianAPIError):
    """429 exhausted all backoff retries."""


class PageNotFoundError(AgentKitError):
    """Confluence page lookup bt space+title matched nothing."""


class InvalidTransitionError(AgentKitError):
    """Requested Jira workflow transition is not allowed from the current status."""