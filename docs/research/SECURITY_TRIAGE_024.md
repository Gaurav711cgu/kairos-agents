# T5 security triage: ruff --select S, 17 findings (ruff 3.14 global binary; .venv has no ruff). Verdict: 0 REAL, 17 SAFE.
Hardening notes (not defects): H1 sandbox.py:277 argv uses case['image']/case['command'] from the operator-owned registry; an image beginning with '-' would be parsed as a docker option. Trusted input, no exploit path from API users.

| finding | verdict | reason |
|---|---|---|
| evaluation.py:29 S311 | SAFE | random.Random(fixed seed) builds a deterministic synthetic task suite; not security use |
| evaluation.py:146 S608 | SAFE | WHERE fragment chosen from two literals ('published=true' / 'tenant_id=%s'); values bound via %s |
| evaluation.py:150 S608 | SAFE | same; id/tenant bound params |
| identity.py:281 S106 | SAFE | "client_secret_basic" is an OAuth auth-method name, not a secret; secret comes from config |
| investigations/output_supervisor.py:28 S606 | SAFE | os.execvp of argv built by sandbox.checks (docker argv list); module only run via sys.executable by host; no shell; limit validated 1..MAXIMUM_BYTES |
| investigations/patches.py:38 S607 | SAFE | fixed ['git','apply','--numstat','-']; patch via stdin; headers regex-limited to [ab]/[A-Za-z0-9_./-]+ and source_path()-checked; non-100644 modes/renames/binary rejected; timeout 5 |
| investigations/patches.py:49 S603 | SAFE | fixed git apply --check / apply; argv constants; patch via stdin only after validation |
| investigations/repository.py:125 S608 | SAFE | where = literal ('published=true'|'tenant_id=%s') + literal cursor clause; cursor values parsed (datetime, UUID) and bound; LIMIT bound |
| investigations/repository.py:221 S608 | SAFE | counter comes from fixed dict keyed by kind/name (model_calls|patch_count|check_count), None otherwise; column never from request text |
| investigations/sandbox.py:257 S607 | SAFE | fixed git apply of registry test.patch in a temp copy |
| investigations/sandbox.py:277 S603 | SAFE | docker rm -f of self-generated name 'kairos-check-'+uuid4().hex; list argv |
| investigations/sandbox.py:299 S603 | SAFE | list argv, no shell; sys.executable + fixed supervisor; docker flags hardcoded (network none, read-only, cap-drop, user 10001, mem/pids caps); image/command from registry (see H1) |
| investigations/sandbox.py:299 S607 | SAFE | 'docker' partial path (PATH trust of host operator) |
| jobs_repository.py:182 S608 | SAFE | WHERE from two literals; tenant bound |
| repository.py:109 S608 | SAFE | condition from two literals; run_id validated by UUID() and bound |
| scripts/localization_dev024.py:316-317 S607 | SAFE | fixed git rev-parse / status in PROJECT; offline tooling |
