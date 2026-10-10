CREATE TABLE IF NOT EXISTS kairos_evaluations (
 id uuid PRIMARY KEY, tenant_id text NOT NULL, published boolean NOT NULL DEFAULT false,
 report jsonb NOT NULL, created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS kairos_evaluations_tenant_created ON kairos_evaluations(tenant_id,created_at DESC);
