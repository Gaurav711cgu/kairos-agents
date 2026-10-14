-- Expand once without scanning the existing table under the exclusive lock.
ALTER TABLE kairos_investigations DROP CONSTRAINT kairos_investigations_configuration_check;
ALTER TABLE kairos_investigations ADD CONSTRAINT kairos_investigations_configuration_check CHECK(configuration IN ('loop-v1','baseline-v1','loop-v2','baseline-v2','loop-v3','baseline-v3','loop-v4','baseline-v4','drafts-v4','loop-v5','baseline-v5','loop-v6','baseline-v6','loop-v7','baseline-v7')) NOT VALID;
