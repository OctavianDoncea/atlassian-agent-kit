"""CLI: ingest a directory of .md/.txt files, or search the corpus."""
from __future__ import annotations
import argparse
import json
import pathlib
from agentkit.rag.ingest import ingest_documents
from agentkit.rag.tool import local_rag_search

def main() -> None:
    p = argparse.ArgumentParser(prog='rag')
    sub = p.add_subparsers(dest='cmd', required=True)
    ing = sub.add_parser('ingest')
    ing.add_argument('--dir', required=True)
    sea = sub.add_parser('search')
    sea.add_argument('--query', required=True)
    sea.add_argument('--k', type=int, default=5)
    args = p.parse_args()

    if args.cmd == 'ingest':
        docs = []
        for f in sorted(pathlib.Path(args.dir).rglob('*')):
            if f.suffix in {'.md', '.txt'}:
                docs.append({'source': str(f), 'content': f.read_text(encoding='utf-8')})
        report = ingest_documents(docs)
        print(json.dumps({'added': report.added, 'skipped': report.skipped, 'sources': report.sources}))
    else:
        print(json.dumps(local_rag_search(args.query, k=args.k), indent=2))

if __name__ == '__main__':
    main()