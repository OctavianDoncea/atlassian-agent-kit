#!/usr/bin/env python3
from __future__ import annotations
import argparse
import asyncio
import time
from agentkit.integrations.sync_pipeline import build_async_confluence_client, sync_space, sync_space_concurrently

async def benchmark(space_key: str, limit: int, concurrency: int) -> tuple[float, float]:
    async with build_async_confluence_client(concurrency=1) as seq:
        ids = [p['id'] for p in await seq.list_pages(space_key, limit=limit)]
        t0 = time.perf_counter()

        for pid in ids:
            await seq.get_page_markdown(pid)

        seq_s = time.perf_counter() - t0

    async with build_async_confluence_client(concurrency=concurrency) as con:
        t0 = time.perf_counter()
        await con.batch_fetch_markdown(ids)
        con_s = time.perf_counter() - t0

    return seq_s, con_s

async def run(args: argparse.Namespace) -> None:
    if args.benchmark:
        seq_s, con_s, n = await benchmark(args.space, args.limit, args.concurrency)
        speedup = seq_s / con_s if con_s else float('inf')
        print(f'benchmark: {n} pages | sequential {seq_s:.2f}s | concurrent({args.concurrency}) {con_s:.2f}s | speedup {speedup:.1f}x')
    report = await sync_space_concurrently(args.space, concurrency=args.concurrency, max_pages=args.limit)
    print(f'sync {report.space_key}: seen={report.pages_seen} created={report.created} updated={report.updated} unchanged={report.unchanged} errors={len(report.errors)} in {report.duration_s:.2f}s')

    for err in report.errors[:5]:
        print('  !', err)

def main() -> None:
    ap = argparse.ArgumentParser(description='Concurrent Confluence -> Postgres sync')
    ap.add_argument('--space', default='EW')
    ap.add_argument('--concurrency', type=int, default=8)
    ap.add_argument('--limit', type=int, default=25)
    ap.add_argument('--benchmark', action='store_true')
    args = ap.parse_args()
    asyncio.run(run(args))

if __name__ == '__main__':
    main()