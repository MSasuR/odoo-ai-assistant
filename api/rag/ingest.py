"""Incremental corpus ingestion: python -m api.rag.ingest [path] [--provider gemini]

Only new or modified chunks are embedded (content hash), so re-running it is cheap and
never duplicates. Chunks of files that were deleted from the corpus are removed too.
"""
import argparse
from pathlib import Path

from api.providers import get_provider
from api.rag import store
from api.rag.chunker import chunk_markdown


def embed_model_id(provider) -> str:
    return f"{provider.name}:{provider.embed_model}"


def ingest(corpus_dir: Path, provider_name: str | None = None) -> dict:
    provider = get_provider(provider_name)
    model_id = embed_model_id(provider)
    store.ensure_schema()
    stats = {"files": 0, "chunks": 0, "embedded": 0, "removed": 0}
    present: set[str] = set()
    for path in sorted(corpus_dir.rglob("*.md")):
        source = path.relative_to(corpus_dir).as_posix()
        present.add(source)
        chunks = chunk_markdown(path.read_text(encoding="utf-8"), source)
        if not chunks:
            continue
        known = store.known_hashes(source, model_id)
        new = [c for c in chunks if store.content_hash(c) not in known]
        vectors = provider.embed([c.text_for_embedding for c in new]) if new else []
        store.sync_source(source, model_id, chunks, new, vectors)
        stats["files"] += 1
        stats["chunks"] += len(chunks)
        stats["embedded"] += len(new)
    stats["removed"] = store.delete_missing_sources(present, model_id)
    return stats


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("path", nargs="?", default="corpus")
    ap.add_argument("--provider", default=None)
    a = ap.parse_args()
    print(ingest(Path(a.path), a.provider))
