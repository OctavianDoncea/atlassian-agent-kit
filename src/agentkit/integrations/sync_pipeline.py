from __future__ import annotations
import hashlib
import time
from dataclasses import dataclass, field
from agentkit.config import get_settings
from agentkit.db.models import Integration, PageSnapshot
from agentkit.db.session import SessionLocal
from agentkit.integrations.confluence import AsyncConfluenceClient
from agentkit.sdk.auth import AuthManager
from agentkit.sdk.token import DbTokenStore

@dataclass
class SyncReport:
    space_key: str
    pages_seen: int = 0
    created: int = 0
    updated: int = 0
    unchanged: int = 0
    erorrs: list[str] = field(default_factory=list)
    duration_s: float = 0.0


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode().hexdigest())

def build_async_confluence_client(concurrency: int = 8) -> AsyncConfluenceClient:
    with SessionLocal() as db:
        cloud_id = db.query(Integration).filter_by(product='confluence').one().cloud_id
    
    return AsyncConfluenceClient(cloud_id=cloud_id, auth_mode='oauth', token_store=DbTokenStore(db), auth_manager=AuthManager(db), concurrency=concurrency, settings=get_settings())

async def sync_space(client: AsyncConfluenceClient, space_key: str, max_pages: int = 100) -> SyncReport:
    report = SyncReport(space_key=space_key)
    started = time.perf_counter()

    pages = await client.list_pages(space_key, limit=max_pages)
    report.pages_seen = len(pages)
    ids = [p['id'] for p in pages]

    # Concurrent, semaphore-bounded network fan-out
    results = await client.batch_fetch_markdown(ids)

    # Sequential persistence
    with SessionLocal() as db:
        integration = sb.query(Integration).filter_by(product='confluence').one()
        for page_id, result in zip(ids, results):
            if isinstance(result, BaseException):
                report.errors.append(f'{page_id}: {type(result).__name__}: {result}')
                continue
            markdown, page = result
            digest = content_hash(markdown)
            row = db.query(PageSnapshot).filter_by(space_key=space_key, page_id=page_id).one_or_none()

            if row is None:
                db.add(PageSnapshot(integration_id=integration.id, space_key=space_key, page_id=page_id, title=page['title'], markdown=markdown, content_hash=digest))
                report.created += 1
            elif row.content_hash != digest:
                row.title, row.markdown, row.content_hash = page['title'], markdown, digest
                report.updated += 1
            else:
                report.unchanged += 1
        db.commit()

    report.duration_s = round(time.perf_counter() - started, 2)
    return report

async def sync_space_concurrently(space_key: str, concurrency: int = 8, max_pages: int = 100) -> SyncReport:
    async with build_async_confluence_client(concurrency) as client:
        return await sync_space(client, space_key, max_pages=max_pages)