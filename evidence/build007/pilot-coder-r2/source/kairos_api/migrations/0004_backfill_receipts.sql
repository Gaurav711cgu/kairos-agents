CREATE TABLE kairos_data_backfills (
 name text PRIMARY KEY, checksum text NOT NULL, cursor_id uuid, updated_rows bigint NOT NULL DEFAULT 0,
 skipped_rows bigint NOT NULL DEFAULT 0, completed boolean NOT NULL DEFAULT false,
 updated_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
