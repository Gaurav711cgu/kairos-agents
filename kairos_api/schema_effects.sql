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
