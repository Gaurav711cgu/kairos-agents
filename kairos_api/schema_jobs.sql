CREATE TABLE IF NOT EXISTS kairos_jobs (
 id uuid PRIMARY KEY, tenant_id text NOT NULL, command_key text NOT NULL,
 command_digest text NOT NULL, scenario_id text NOT NULL, policy text NOT NULL,
 runner text NOT NULL, publish boolean NOT NULL DEFAULT false,
 parent_job_id uuid REFERENCES kairos_jobs(id), status text NOT NULL DEFAULT 'queued',
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(), updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 deadline_at timestamptz NOT NULL, attempt integer NOT NULL DEFAULT 0, max_attempts integer NOT NULL DEFAULT 3,
 model_calls integer NOT NULL DEFAULT 0, cancel_requested boolean NOT NULL DEFAULT false,
 lease_owner text, lease_token bigint NOT NULL DEFAULT 0, lease_expires_at timestamptz,
 checkpoint_version integer NOT NULL DEFAULT 1, stage text NOT NULL DEFAULT 'prepared',
 context_blocks jsonb NOT NULL, input_digest text NOT NULL,
 request jsonb, response jsonb, result jsonb, error jsonb,
 UNIQUE (tenant_id, command_key), CHECK (model_calls BETWEEN 0 AND 1)
);
CREATE INDEX IF NOT EXISTS kairos_jobs_queue_idx ON kairos_jobs(status,created_at);
CREATE INDEX IF NOT EXISTS kairos_jobs_tenant_idx ON kairos_jobs(tenant_id,created_at DESC);
CREATE TABLE IF NOT EXISTS kairos_job_events (
 job_id uuid NOT NULL REFERENCES kairos_jobs(id), seq integer NOT NULL,
 event_type text NOT NULL, payload jsonb NOT NULL, created_at timestamptz NOT NULL,
 prev_hash text NOT NULL, event_hash text NOT NULL, PRIMARY KEY(job_id,seq)
);

ALTER TABLE kairos_jobs ADD COLUMN IF NOT EXISTS input_snapshot jsonb;
