from __future__ import annotations
from dataclasses import dataclass, field
from agentkit.db.models import DocumentChunk
from agentkit.db.session import SessionLocal
from agentkit.rag.chunking import chunk_document
from agentkit.rag.embeddings import embed_texts

@dataclass
class IngestReport:
    added: int = 0
    skipped: int= 0
    sources: list[str] = field(default_factory=list)


def ingest_documents(docs: list[dict], client = None, replace_source: bool = False) -> IngestReport:
    report = IngestReport()
    chunks = []

    for d in docs:
        chunks.extend(chunk_document(d['source'], d['content'], d.get('page')))

        if d['source'] not in report.sources:
            report.sources.append(d['source'])

    if not chunks:
        return report

    with SessionLocal() as db:
        if replace_source:
            for s in report.sources:
                db.query(DocumentChunk).filter_by(source=s).delete()
        else:
            hashes = {c.content_hash for c in chunks}
            existing = {r[0] for r in db.query(DocumentChunk.content_hash).filter(DocumentChunk.content_hash.in_(hashes)).all()}
            report.skipped = len(existing)
            chunks = [c for c in chunks if c.content_hash not in existing]

        vectors = embed_texts([c.content for c in chunks], client=client)

        for c, v in zip(chunks, vectors):
            db.add(DocumentChunk(
                source=c.source, page=c.page, chunk_index=c.chunk_index, content_hash=c.content_hash, content=c.content,
                token_count=c.token_count, embedding=v
            ))
            report.added += 1

        db.commit()

    return report