"""Vector store on pgvector (`pgvector` container, `rag` database)."""
import hashlib

import psycopg
from psycopg.rows import dict_row

from api.config import settings
from api.providers.gemini import EMBED_DIM
from api.rag.chunker import Chunk

SCHEMA = f"""
CREATE EXTENSION IF NOT EXISTS vector;
CREATE TABLE IF NOT EXISTS chunks (
    id           BIGSERIAL PRIMARY KEY,
    source       TEXT NOT NULL,
    heading      TEXT NOT NULL,
    content      TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    embed_model  TEXT NOT NULL,          -- vectors from different models are never mixed
    embedding    vector({EMBED_DIM}) NOT NULL,
    UNIQUE (source, content_hash, embed_model)
);
CREATE INDEX IF NOT EXISTS chunks_embedding_idx
    ON chunks USING hnsw (embedding vector_cosine_ops);
"""


def connect():
    return psycopg.connect(settings.vector_db_dsn, row_factory=dict_row, connect_timeout=5)


def ensure_schema() -> None:
    with connect() as conn:
        conn.execute(SCHEMA)


def to_vec(v: list[float]) -> str:
    return "[" + ",".join(f"{x:.7f}" for x in v) + "]"


def content_hash(c: Chunk) -> str:
    return hashlib.sha256(f"{c.heading}\n{c.content}".encode()).hexdigest()[:32]


def known_hashes(source: str, embed_model: str) -> set[str]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT content_hash FROM chunks WHERE source = %s AND embed_model = %s", (source, embed_model)
        ).fetchall()
    return {r["content_hash"] for r in rows}


def sync_source(source: str, embed_model: str, all_chunks: list[Chunk],
                new_chunks: list[Chunk], new_vectors: list[list[float]]) -> None:
    """Leave exactly the chunks of `source` in the DB: delete those no longer in the
    file and insert only the new ones (existing chunks keep their embedding)."""
    keep = [content_hash(c) for c in all_chunks]
    with connect() as conn:
        conn.execute(
            "DELETE FROM chunks WHERE source = %s AND embed_model = %s AND content_hash <> ALL(%s)",
            (source, embed_model, keep),
        )
        for c, v in zip(new_chunks, new_vectors, strict=True):
            conn.execute(
                "INSERT INTO chunks (source, heading, content, content_hash, embed_model, embedding) "
                "VALUES (%s, %s, %s, %s, %s, %s::vector) ON CONFLICT DO NOTHING",
                (c.source, c.heading, c.content, content_hash(c), embed_model, to_vec(v)),
            )


def delete_missing_sources(present: set[str], embed_model: str) -> int:
    """Remove the chunks of sources whose file no longer exists. Returns the rows deleted.

    Safety: with an empty `present` set nothing is deleted (an empty or unmounted corpus
    directory must not wipe the whole index)."""
    if not present:
        return 0
    with connect() as conn:
        cur = conn.execute(
            "DELETE FROM chunks WHERE embed_model = %s AND source <> ALL(%s)",
            (embed_model, sorted(present)),
        )
        return cur.rowcount


def search(vector: list[float], embed_model: str, k: int) -> list[dict]:
    with connect() as conn:
        return conn.execute(
            "SELECT source, heading, content, 1 - (embedding <=> %s::vector) AS score "
            "FROM chunks WHERE embed_model = %s ORDER BY embedding <=> %s::vector LIMIT %s",
            (to_vec(vector), embed_model, to_vec(vector), k),
        ).fetchall()
