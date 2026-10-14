-- Kairos Enterprise Database Schema v2
-- Production Multi-Tenant Relational Foundation, Declarative Range Partitioning,
-- Content-Addressed Blob Registry, Transactional Outbox, and Row-Level Security (RLS).
-- Zero emojis invariant enforced.

-- 1. Multi-Tenant Organization Schema
CREATE TABLE IF NOT EXISTS tenants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slug VARCHAR(64) UNIQUE NOT NULL,
    name VARCHAR(128) NOT NULL,
    plan VARCHAR(32) NOT NULL DEFAULT 'standard',
    rate_limit_per_min INT NOT NULL DEFAULT 5000,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 2. Machine-to-Machine Scoped API Keys
CREATE TABLE IF NOT EXISTS api_keys (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    key_prefix VARCHAR(16) NOT NULL,
    key_hash CHAR(64) NOT NULL,
    scopes TEXT[] NOT NULL DEFAULT '{"ingest", "read"}',
    revoked BOOLEAN NOT NULL DEFAULT FALSE,
    expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_used_at TIMESTAMPTZ
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_api_keys_hash ON api_keys(key_hash) WHERE revoked = FALSE;
CREATE INDEX IF NOT EXISTS idx_api_keys_tenant ON api_keys(tenant_id);

-- 3. Workflow & Agent Runs
CREATE TABLE IF NOT EXISTS runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    parent_run_id UUID REFERENCES runs(id) ON DELETE SET NULL,
    scenario_id VARCHAR(64) NOT NULL,
    policy VARCHAR(32) NOT NULL DEFAULT 'preserve',
    runner VARCHAR(64) NOT NULL DEFAULT 'reference',
    status VARCHAR(32) NOT NULL DEFAULT 'running',
    idempotency_key VARCHAR(128),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT uq_tenant_idempotency UNIQUE(tenant_id, idempotency_key)
);
CREATE INDEX IF NOT EXISTS idx_runs_tenant_created ON runs(tenant_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_runs_parent ON runs(parent_run_id) WHERE parent_run_id IS NOT NULL;

-- 4. Content-Addressed Blob Storage Registry
CREATE TABLE IF NOT EXISTS blobs (
    digest CHAR(64) PRIMARY KEY,
    byte_size BIGINT NOT NULL,
    content_type VARCHAR(64) NOT NULL DEFAULT 'application/json',
    storage_path VARCHAR(256) NOT NULL,
    ref_count INT NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 5. Append-Only Steps (Partitioned by Range on created_at)
CREATE TABLE IF NOT EXISTS steps (
    run_id UUID NOT NULL,
    seq INT NOT NULL,
    tenant_id UUID NOT NULL,
    event_type VARCHAR(64) NOT NULL,
    title VARCHAR(128) NOT NULL,
    payload JSONB NOT NULL,
    blob_digest CHAR(64) REFERENCES blobs(digest) ON DELETE RESTRICT,
    event_hash CHAR(64) NOT NULL,
    prev_hash CHAR(64) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (run_id, seq, created_at)
) PARTITION BY RANGE (created_at);

-- Partition Tables
CREATE TABLE IF NOT EXISTS steps_y2026m10 PARTITION OF steps
    FOR VALUES FROM ('2026-10-01 00:00:00+00') TO ('2026-11-01 00:00:00+00');
CREATE TABLE IF NOT EXISTS steps_y2026m11 PARTITION OF steps
    FOR VALUES FROM ('2026-11-01 00:00:00+00') TO ('2026-12-01 00:00:00+00');
CREATE TABLE IF NOT EXISTS steps_y2026m12 PARTITION OF steps
    FOR VALUES FROM ('2026-12-01 00:00:00+00') TO ('2027-01-01 00:00:00+00');
CREATE TABLE IF NOT EXISTS steps_default PARTITION OF steps DEFAULT;

-- Composite B-Tree for timeline scrubbing and parent context resolution
CREATE INDEX IF NOT EXISTS idx_steps_run_seq ON steps (run_id, seq ASC);

-- GIN Index with jsonb_path_ops for deep arbitrary JSON queries on tool payloads
CREATE INDEX IF NOT EXISTS idx_steps_payload_gin ON steps USING gin (payload jsonb_path_ops);

-- BRIN Index for cost-free historical partition range filtering
CREATE INDEX IF NOT EXISTS idx_steps_created_brin ON steps USING brin (created_at);

-- 6. Transactional Outbox Table (Partitioned by Range on created_at)
CREATE TABLE IF NOT EXISTS outbox (
    id BIGSERIAL,
    event_id UUID NOT NULL DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    aggregate_type VARCHAR(64) NOT NULL,
    aggregate_id VARCHAR(64) NOT NULL,
    event_type VARCHAR(64) NOT NULL,
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    processed_at TIMESTAMPTZ,
    retry_count INT NOT NULL DEFAULT 0,
    last_error TEXT,
    PRIMARY KEY (id, created_at)
) PARTITION BY RANGE (created_at);

-- Outbox Partitions
CREATE TABLE IF NOT EXISTS outbox_y2026m10 PARTITION OF outbox
    FOR VALUES FROM ('2026-10-01 00:00:00+00') TO ('2026-11-01 00:00:00+00');
CREATE TABLE IF NOT EXISTS outbox_y2026m11 PARTITION OF outbox
    FOR VALUES FROM ('2026-11-01 00:00:00+00') TO ('2026-12-01 00:00:00+00');
CREATE TABLE IF NOT EXISTS outbox_y2026m12 PARTITION OF outbox
    FOR VALUES FROM ('2026-12-01 00:00:00+00') TO ('2027-01-01 00:00:00+00');
CREATE TABLE IF NOT EXISTS outbox_default PARTITION OF outbox DEFAULT;

-- Partial Index for high-throughput outbox dispatch (scans only unprocessed rows)
CREATE INDEX IF NOT EXISTS idx_outbox_unprocessed ON outbox (id, created_at)
WHERE processed_at IS NULL;

-- 7. Row-Level Security (RLS) Policies
ALTER TABLE runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE steps ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies WHERE policyname = 'tenant_isolation_runs' AND tablename = 'runs'
    ) THEN
        CREATE POLICY tenant_isolation_runs ON runs
            FOR ALL
            USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_policies WHERE policyname = 'tenant_isolation_steps' AND tablename = 'steps'
    ) THEN
        CREATE POLICY tenant_isolation_steps ON steps
            FOR ALL
            USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid);
    END IF;
END $$;
