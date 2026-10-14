"""Publish four actually executed synthetic runs; repeat invocations are idempotent."""
import json

from kairos_api.repository import RunRepository
from kairos_api.settings import Settings


def main() -> None:
    settings = Settings.from_environment()
    if not settings.credentials:
        raise SystemExit("Configure KAIROS_DEV_TOKEN or KAIROS_DEVELOPER_CREDENTIALS before seeding.")
    tenant_id = next(iter(settings.credentials.values()))
    repository = RunRepository(settings.database_url)
    repository.initialize()
    runs = []
    for scenario_id in ("late-order-exception", "late-order-standard", "insufficient-evidence"):
        runs.append(repository.create(tenant_id, f"build001.seed.{scenario_id}",
                                      {"scenario_id": scenario_id, "policy": "compact", "publish": True}))
    runs.append(repository.create(tenant_id, "build001.seed.preserve-fork", {"policy": "preserve"}, parent_run_id=runs[0]["id"]))
    print(json.dumps({"executed_or_reused_runs": [{"id": run["id"], "scenario_id": run["scenario_id"],
                                                "policy": run["policy"], "grade_passed": run["grade_passed"]} for run in runs]}, indent=2))


if __name__ == "__main__":
    main()
