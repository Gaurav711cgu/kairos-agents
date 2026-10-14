CREATE TABLE IF NOT EXISTS kairos_investigations (
 id uuid PRIMARY KEY, tenant_id text NOT NULL, command_key text NOT NULL, command_digest text NOT NULL,
 task_id text NOT NULL, task_snapshot jsonb NOT NULL, task_digest text NOT NULL,
 configuration text NOT NULL CHECK(configuration IN ('loop-v1','baseline-v1','loop-v2','baseline-v2','loop-v3','baseline-v3','loop-v4','baseline-v4','drafts-v4','loop-v5','baseline-v5')), config_snapshot jsonb NOT NULL,
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

ALTER TABLE kairos_investigations DROP CONSTRAINT IF EXISTS kairos_investigations_configuration_check;
ALTER TABLE kairos_investigations ADD CONSTRAINT kairos_investigations_configuration_check CHECK(configuration IN ('loop-v1','baseline-v1','loop-v2','baseline-v2','loop-v3','baseline-v3','loop-v4','baseline-v4','drafts-v4','loop-v5','baseline-v5'));

ALTER TABLE kairos_investigations ADD COLUMN IF NOT EXISTS config_digest text;

-- Build004: keyset lists. Additive indexes preserve historical rows.
CREATE INDEX IF NOT EXISTS kairos_investigation_tenant_listing ON kairos_investigations(tenant_id,created_at DESC,id DESC);
CREATE INDEX IF NOT EXISTS kairos_investigation_public_listing ON kairos_investigations(created_at DESC,id DESC) WHERE published=true;

ALTER TABLE kairos_investigations ADD COLUMN IF NOT EXISTS registry_version text NOT NULL DEFAULT 'repository-cases-v1';
