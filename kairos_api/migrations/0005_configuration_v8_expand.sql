-- Expand configuration and all physical counters together; preserve historical bounds.
ALTER TABLE kairos_investigations ADD CONSTRAINT kairos_investigations_configuration_v8_check CHECK (configuration IN ('loop-v1','baseline-v1','loop-v2','baseline-v2','loop-v3','baseline-v3','loop-v4','baseline-v4','drafts-v4','loop-v5','baseline-v5','loop-v6','baseline-v6','loop-v7','baseline-v7','loop-v8','baseline-v8')) NOT VALID;
ALTER TABLE kairos_investigations DROP CONSTRAINT kairos_investigations_configuration_check;
ALTER TABLE kairos_investigations RENAME CONSTRAINT kairos_investigations_configuration_v8_check TO kairos_investigations_configuration_check;
ALTER TABLE kairos_investigations ADD CONSTRAINT kairos_investigations_model_calls_v8_check CHECK (model_calls BETWEEN 0 AND CASE configuration WHEN 'loop-v8' THEN 10 WHEN 'baseline-v8' THEN 1 ELSE 6 END) NOT VALID;
ALTER TABLE kairos_investigations DROP CONSTRAINT kairos_investigations_model_calls_check;
ALTER TABLE kairos_investigations RENAME CONSTRAINT kairos_investigations_model_calls_v8_check TO kairos_investigations_model_calls_check;
ALTER TABLE kairos_investigations ADD CONSTRAINT kairos_investigations_patch_count_v8_check CHECK (patch_count BETWEEN 0 AND CASE configuration WHEN 'loop-v8' THEN 4 WHEN 'baseline-v8' THEN 1 ELSE 2 END) NOT VALID;
ALTER TABLE kairos_investigations DROP CONSTRAINT kairos_investigations_patch_count_check;
ALTER TABLE kairos_investigations RENAME CONSTRAINT kairos_investigations_patch_count_v8_check TO kairos_investigations_patch_count_check;
ALTER TABLE kairos_investigations ADD CONSTRAINT kairos_investigations_check_count_v8_check CHECK (check_count BETWEEN 0 AND CASE configuration WHEN 'loop-v8' THEN 4 WHEN 'baseline-v8' THEN 1 ELSE 2 END) NOT VALID;
ALTER TABLE kairos_investigations DROP CONSTRAINT kairos_investigations_check_count_check;
ALTER TABLE kairos_investigations RENAME CONSTRAINT kairos_investigations_check_count_v8_check TO kairos_investigations_check_count_check;
