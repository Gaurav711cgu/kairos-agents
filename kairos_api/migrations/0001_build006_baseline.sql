-- Canonical build006 schema. Existing complete schemas are validated before adoption.
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
 context_blocks jsonb NOT NULL, input_digest text NOT NULL, input_snapshot jsonb,
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



CREATE TABLE IF NOT EXISTS kairos_effect_proposals (
 id uuid PRIMARY KEY, tenant_id text NOT NULL, run_id uuid NOT NULL REFERENCES kairos_runs(id),
 proposal jsonb NOT NULL, digest text NOT NULL, version integer NOT NULL DEFAULT 1,
 state text NOT NULL DEFAULT 'proposed' CHECK(state IN ('proposed','approved','applied','revoked')),
 approved_by text, approval_expires_at timestamptz, created_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(tenant_id,run_id)
);
CREATE TABLE IF NOT EXISTS kairos_sandbox_adjustments (
 id uuid PRIMARY KEY, tenant_id text NOT NULL, order_id text NOT NULL, target_digest text NOT NULL,
 amount_cents integer NOT NULL CHECK(amount_cents>0), proposal_id uuid NOT NULL REFERENCES kairos_effect_proposals(id),
 created_at timestamptz NOT NULL DEFAULT now(), UNIQUE(tenant_id,order_id)
);
CREATE TABLE IF NOT EXISTS kairos_effect_commands (
 tenant_id text NOT NULL, command_key text NOT NULL, digest text NOT NULL, result jsonb,
 PRIMARY KEY(tenant_id,command_key)
);

CREATE TABLE IF NOT EXISTS kairos_evaluations (
 id uuid PRIMARY KEY, tenant_id text NOT NULL, published boolean NOT NULL DEFAULT false,
 report jsonb NOT NULL, created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS kairos_evaluations_tenant_created ON kairos_evaluations(tenant_id,created_at DESC);

CREATE TABLE IF NOT EXISTS kairos_memberships (
 subject text PRIMARY KEY,
 tenant_id text NOT NULL,
 role text NOT NULL CHECK(role IN ('viewer','operator','admin')),
 active boolean NOT NULL DEFAULT true,
 updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS kairos_login_states (
 state_hash text PRIMARY KEY,
 verifier text NOT NULL,
 nonce text NOT NULL,
 binding_hash text NOT NULL,
 return_to text NOT NULL,
 expires_at timestamptz NOT NULL
);
CREATE TABLE IF NOT EXISTS kairos_sessions (
 session_hash text PRIMARY KEY,
 subject text NOT NULL REFERENCES kairos_memberships(subject),
 expires_at timestamptz NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS kairos_sessions_expiry ON kairos_sessions(expires_at);

CREATE TABLE IF NOT EXISTS kairos_investigations (
 id uuid PRIMARY KEY, tenant_id text NOT NULL, command_key text NOT NULL, command_digest text NOT NULL,
 task_id text NOT NULL, task_snapshot jsonb NOT NULL, task_digest text NOT NULL,
 configuration text NOT NULL CHECK(configuration IN ('loop-v1','baseline-v1','loop-v2','baseline-v2','loop-v3','baseline-v3','loop-v4','baseline-v4','drafts-v4','loop-v5','baseline-v5','loop-v6','baseline-v6')), config_snapshot jsonb NOT NULL, config_digest text,
 registry_version text NOT NULL DEFAULT 'repository-cases-v1',
 parent_id uuid REFERENCES kairos_investigations(id), published boolean NOT NULL DEFAULT false,
 status text NOT NULL DEFAULT 'queued' CHECK(status IN ('queued','running','completed','failed','cancelled','unknown','timed_out')),
 outcome text, summary text, created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 updated_at timestamptz NOT NULL DEFAULT clock_timestamp(), started_at timestamptz, deadline_at timestamptz,
 lease_owner text, lease_token bigint NOT NULL DEFAULT 0, lease_expires_at timestamptz,
 cancel_requested boolean NOT NULL DEFAULT false, claims integer NOT NULL DEFAULT 0,
 model_calls integer NOT NULL DEFAULT 0 CHECK(model_calls BETWEEN 0 AND 6),
 patch_count integer NOT NULL DEFAULT 0 CHECK(patch_count BETWEEN 0 AND 2),
 check_count integer NOT NULL DEFAULT 0 CHECK(check_count BETWEEN 0 AND 2),
 UNIQUE(tenant_id,command_key)
);
CREATE INDEX IF NOT EXISTS kairos_investigation_queue ON kairos_investigations(created_at) WHERE status='queued';
CREATE TABLE IF NOT EXISTS kairos_investigation_steps (
 investigation_id uuid NOT NULL REFERENCES kairos_investigations(id), seq integer NOT NULL,
 kind text NOT NULL CHECK(kind IN ('context','model','tool')), name text NOT NULL,
 state text NOT NULL CHECK(state IN ('pending','captured')),
 request jsonb NOT NULL, result jsonb, started_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 captured_at timestamptz, PRIMARY KEY(investigation_id,seq)
);
CREATE TABLE IF NOT EXISTS kairos_investigation_artifacts (
 investigation_id uuid NOT NULL REFERENCES kairos_investigations(id), sha256 text NOT NULL,
 bytes bigint NOT NULL CHECK(bytes>=0), PRIMARY KEY(investigation_id,sha256)
);



-- Build004: keyset lists. Additive indexes preserve historical rows.
CREATE INDEX IF NOT EXISTS kairos_investigation_tenant_listing ON kairos_investigations(tenant_id,created_at DESC,id DESC);
CREATE INDEX IF NOT EXISTS kairos_investigation_public_listing ON kairos_investigations(created_at DESC,id DESC) WHERE published=true;

