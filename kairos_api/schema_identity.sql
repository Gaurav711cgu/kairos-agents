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
