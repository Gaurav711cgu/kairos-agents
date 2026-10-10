"""Create local credentials once. Never prints their values."""
import secrets
from pathlib import Path

root = Path(__file__).resolve().parents[1]
config = root / ".env.kairos.local"
if not config.exists():
    password = secrets.token_urlsafe(32)
    token = secrets.token_urlsafe(32)
    config.write_text(f"KAIROS_POSTGRES_PASSWORD={password}\nDATABASE_URL=postgresql://kairos:{password}@127.0.0.1:55432/kairos\nTEST_DATABASE_URL=postgresql://kairos:{password}@127.0.0.1:55432/kairos\nKAIROS_DEV_TOKEN={token}\nKAIROS_DEV_TENANT=local-studio\n")
    config.chmod(0o600)
values = dict(line.split("=", 1) for line in config.read_text().splitlines() if line and not line.startswith("#"))
web_config = root / "dashboard/.env.local"
if not web_config.exists():
    web_config.write_text(f"KAIROS_API_URL=http://127.0.0.1:8100\nKAIROS_DEV_TOKEN={values['KAIROS_DEV_TOKEN']}\nKAIROS_ENABLE_LOCAL_MUTATIONS=true\n")
    web_config.chmod(0o600)
print("Local configuration ready; existing files preserved. No credential values printed.")
