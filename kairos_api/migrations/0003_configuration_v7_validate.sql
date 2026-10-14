-- Validate separately using PostgreSQL's weaker validation lock.
ALTER TABLE kairos_investigations VALIDATE CONSTRAINT kairos_investigations_configuration_check;
