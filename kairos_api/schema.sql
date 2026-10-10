CREATE TABLE IF NOT EXISTS kairos_runs (
    id uuid PRIMARY KEY,
    tenant_id text NOT NULL,
    published boolean NOT NULL DEFAULT false,
    document jsonb NOT NULL,
    document_hash text NOT NULL,
    event_count integer NOT NULL CHECK (event_count > 0),
    event_head text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS kairos_runs_tenant_created ON kairos_runs (tenant_id, created_at DESC);
CREATE INDEX IF NOT EXISTS kairos_runs_public_created ON kairos_runs (created_at DESC) WHERE published;
CREATE TABLE IF NOT EXISTS kairos_events (
    run_id uuid NOT NULL REFERENCES kairos_runs(id) ON DELETE CASCADE,
    seq integer NOT NULL CHECK (seq > 0),
    event jsonb NOT NULL,
    PRIMARY KEY (run_id, seq)
);
CREATE TABLE IF NOT EXISTS kairos_commands (
    tenant_id text NOT NULL,
    idempotency_key text NOT NULL,
    request_digest text NOT NULL,
    run_id uuid REFERENCES kairos_runs(id),
    PRIMARY KEY (tenant_id, idempotency_key)
);
