-- PostgreSQL Production Schema for Kairos for Agents
-- Includes partitioning on steps, transactional outbox, and content-addressed blobs

CREATE TABLE IF NOT EXISTS runs (
    run_id UUID PRIMARY KEY,
    agent_id TEXT NOT NULL,
    version TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('RUNNING', 'COMPLETED', 'FAILED', 'CANCELLED')),
    task_prompt TEXT NOT NULL,
    config_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS steps (
    run_id UUID NOT NULL,
    seq_id INT NOT NULL,
    event_type TEXT NOT NULL,
    payload JSONB NOT NULL,
    prev_event_hash CHAR(64) NOT NULL,
    event_hash CHAR(64) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (run_id, seq_id)
) PARTITION BY RANGE (created_at);

-- Initial Monthly Partition
CREATE TABLE IF NOT EXISTS steps_y2026m10 PARTITION OF steps
    FOR VALUES FROM ('2026-10-01 00:00:00+00') TO ('2026-11-01 00:00:00+00');

-- Content-Addressed Blobs (SHA-256 deduplicated context chunks)
CREATE TABLE IF NOT EXISTS context_blobs (
    blob_hash CHAR(64) PRIMARY KEY,
    byte_size INT NOT NULL,
    mime_type TEXT NOT NULL DEFAULT 'application/json',
    storage_uri TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Transactional Outbox Table for Asynchronous Relay
CREATE TABLE IF NOT EXISTS outbox_events (
    outbox_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    aggregate_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    payload JSONB NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('PENDING', 'PROCESSED', 'FAILED')),
    retry_count INT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    processed_at TIMESTAMPTZ
);

-- Indexes optimized for EXPLAIN ANALYZE queries
CREATE INDEX IF NOT EXISTS idx_runs_created_at ON runs (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_outbox_pending ON outbox_events (created_at ASC) WHERE status = 'PENDING';
