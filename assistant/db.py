"""Postgres data layer.

One place owns the schema and connections:
- LangGraph checkpointer/store get their own connections (they run .setup()).
- Application tables (routines, device commands, message log, artifacts,
  bounded memory files, device tokens) live in the ``hermes`` schema and are
  accessed through the helpers here. Tools run in worker threads, so the
  sync pool is the default; the server also keeps an async pool.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator

from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool, ConnectionPool

from .config import settings

_SCHEMA_SQL = """
CREATE SCHEMA IF NOT EXISTS hermes;

CREATE TABLE IF NOT EXISTS hermes.routines (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    cron TEXT NOT NULL,
    prompt TEXT NOT NULL,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_run_at TIMESTAMPTZ,
    last_result TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS hermes.device_commands (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    payload JSONB NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'pending',  -- pending | delivered | done | failed
    result TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS hermes.device_tokens (
    token TEXT PRIMARY KEY,
    added_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS hermes.message_log (
    id BIGSERIAL PRIMARY KEY,
    thread_id TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT 'chat',     -- chat | routine | webhook
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS message_log_thread_idx
    ON hermes.message_log (thread_id, id);
CREATE INDEX IF NOT EXISTS message_log_fts_idx
    ON hermes.message_log
    USING GIN (to_tsvector('simple', content));

CREATE TABLE IF NOT EXISTS hermes.threads (
    thread_id TEXT PRIMARY KEY,
    title TEXT NOT NULL DEFAULT '',
    source TEXT NOT NULL DEFAULT 'chat',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS hermes.artifacts (
    id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,                      -- html | markdown | table | chart
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1,
    thread_id TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- The workspace tree: folders/collections at ANY depth, created purely by
-- conversation. No presets — structure exists only because the user asked.
CREATE TABLE IF NOT EXISTS hermes.nodes (
    id TEXT PRIMARY KEY,
    parent_id TEXT REFERENCES hermes.nodes(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    icon TEXT NOT NULL DEFAULT '◇',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS hermes.integrations (
    id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,                      -- mcp | openapi | builtin
    name TEXT NOT NULL,
    config JSONB NOT NULL DEFAULT '{}',
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE hermes.artifacts ADD COLUMN IF NOT EXISTS space TEXT NOT NULL DEFAULT '';

CREATE TABLE IF NOT EXISTS hermes.memory_files (
    name TEXT PRIMARY KEY,                   -- 'MEMORY' | 'USER'
    content TEXT NOT NULL DEFAULT '',
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
INSERT INTO hermes.memory_files (name) VALUES ('MEMORY'), ('USER')
    ON CONFLICT (name) DO NOTHING;
"""

_sync_pool: ConnectionPool | None = None
_async_pool: AsyncConnectionPool | None = None


def sync_pool() -> ConnectionPool:
    global _sync_pool
    if _sync_pool is None:
        _sync_pool = ConnectionPool(
            settings.database_url, min_size=1, max_size=8, open=True,
            kwargs={"row_factory": dict_row},
        )
    return _sync_pool


async def async_pool() -> AsyncConnectionPool:
    global _async_pool
    if _async_pool is None:
        _async_pool = AsyncConnectionPool(
            settings.database_url, min_size=1, max_size=8, open=False,
            kwargs={"row_factory": dict_row},
        )
        await _async_pool.open()
    return _async_pool


@contextmanager
def connection() -> Iterator[Any]:
    """Sync connection with dict rows and autocommit-on-success."""
    with sync_pool().connection() as conn:
        yield conn


def init_schema() -> None:
    """Create application tables. Safe to call on every startup."""
    with connection() as conn:
        conn.execute(_SCHEMA_SQL)


def query(sql: str, params: tuple | dict = ()) -> list[dict]:
    with connection() as conn:
        return conn.execute(sql, params).fetchall()


def execute(sql: str, params: tuple | dict = ()) -> int:
    with connection() as conn:
        return conn.execute(sql, params).rowcount


async def close_pools() -> None:
    global _sync_pool, _async_pool
    if _sync_pool is not None:
        _sync_pool.close()
        _sync_pool = None
    if _async_pool is not None:
        await _async_pool.close()
        _async_pool = None
