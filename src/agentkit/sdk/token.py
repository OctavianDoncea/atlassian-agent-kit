from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Protocol
from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy.orm import sessionmaker
from agentkit.config import get_settings
from agentkit.db.models import OAuthToken
from agentkit.errors import AuthError

@dataclass
class TokenSet:
    access_token: str
    refresh_token: str
    expires_at: datetime
    scope: str | None = None

    @property
    def expired(self) -> bool:
        return datetime.now(timezone.utc) >= self.expires_at - timedelta(seconds=60)


class TokenStoreProtocol(Protocol):
    def load(self, cloud_id: str) -> TokenSet | None: ...
    def save(self, cloud_id: str, site_url: str, tokens: TokenSet) -> None: ...


class DbTokenStore:
    def __init__(self, session_factory: sessionmaker | None = None, key: str | None = None):
        from agentkit.db.session import SessionLocal

        self._session_factory = session_factory or SessionLocal
        key = key or get_settings().token_encryption_key
        if not key:
            raise AuthError('TOKEN_ENCRYPTION_KEY is not set. Run `make keygen` and add it to .env')
        self._fernet = Fernet(key.encode() if isinstance(key, str) else key)

    def load(self, cloud_id: str) -> TokenSet | None:
        with self._session_factory() as db:
            row = db.query(OAuthToken).filter_by(cloud_id=cloud_id).one_or_none()
            if row is None:
                return None
            try:
                return TokenSet(
                    access_token = self._fernet.decrypt(row.access_token.encode()).decode(),
                    refresh_token = self._fernet.decrypt(row.refresh_token.encode()).decode(),
                    expires_at = row.expires_at,
                    scope = row.scope
                )
            except InvalidToken as e:
                raise AuthError('Stored token could not be decrypted (key rotated?). Re-connect OAuth.') from e

    def save(self, cloud_id: str, site_url: str, tokens: TokenSet) -> None:
        with self._session_factory() as db:
            row = db.query(OAuthToken).filter_by(cloud_id=cloud_id).one_or_none()
            if row is None:
                row = OAuthToken(cloud_id=cloud_id, site_url=site_url)
                db.add(row)
            row.access_token = self._fernet.encrypt(tokens.access_token.encode()).decode()
            row.refresh_token = self._fernet.encrypt(tokens.refresh_token.encode()).decode()
            row.scope = tokens.scope
            row.expires_at = tokens.expires_at
            db.commit()