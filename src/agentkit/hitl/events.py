"""Cross-process event bus over Postgres LISTEN/NOTIFY."""
from __future__ import annotations
import asyncio
import json
import logging
import threading
import time
from sqlalchemy import text
from agentkit.config import get_settings
from agentkit.db.session import engine

CHANNEL = 'hitl_events'
_log = logging.getLogger(__name__)

def publish_event(payload: dict) -> None:
    try:
        with engine.connect() as conn:
            conn.execute(text('SELECT pg_notify(:channel, :payload)'), {'channel': CHANNEL, 'payload': json.dumps(payload, default=str)[:7000]})
            conn.commit()
    except Exception as exc:
        _log.warning(f'pg_notify failed (non-fatal): {exc}')

class EventBus:
    """LISTEN notifications to subscribed asyncio queues (SSE clients)."""

    def __init__(self) -> None:
        self._subs: list[tuple[asyncio.AbstractEventLoop, asyncio.Queue]] = []
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        loop = asyncio.get_running_loop()
        with self._lock:
            self._subs.append((loop, q))
            self._ensure_listener()

        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        with self._lock:
            self._subs = [(l, qq) for l, qq in self._subs if qq is not q]

    def _ensure_listener(self) -> None:
        if self._thread and self._thread.is_alive():
            return

        self._thread = threading.Thread(target=self._listen, daemon=True)
        self._thread.start()

    def _listen(self) -> None:
        from psycopg import connect

        url = get_settings().database_url.replace('postgresql+psycopg', 'postgresql', 1)
        while True:
            try:
                with connect(url, autocommit=True) as conn:
                    conn.execute(f'LISTEN {CHANNEL}')
                    while True:
                        for n in conn.notifies(timeout=5):
                            self._fanout(json.loads(n.payload))
            except Exception as exc:
                _log.warning(f'LISTEN loop reconnecting in 2s: {exc}')
                time.sleep(2)

    def _fanout(self, payload: dict) -> None:
        with self._lock:
            subs = list(self._subs)
        for loop, q in subs:
            loop.call_soon_threadsafe(q.put_nowait, payload)


bus = EventBus()