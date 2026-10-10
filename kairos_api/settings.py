"""Developer identity configuration; never accepts browser-supplied tenant IDs."""
from dataclasses import dataclass
import json
import os


def cors_origins() -> list[str]:
    return [value.strip() for value in os.environ.get(
        "KAIROS_CORS_ORIGINS", "http://127.0.0.1:3100,http://localhost:3100").split(",") if value.strip()]


@dataclass(frozen=True)
class Settings:
    database_url: str
    credentials: dict[str, str]
    origins: list[str]

    @classmethod
    def from_environment(cls):
        database_url = os.environ.get("DATABASE_URL", "")
        if not database_url:
            raise ValueError("DATABASE_URL must point to a PostgreSQL database.")
        credentials = json.loads(os.environ.get("KAIROS_DEVELOPER_CREDENTIALS", "{}"))
        if not isinstance(credentials, dict):
            raise ValueError("KAIROS_DEVELOPER_CREDENTIALS must be a JSON object.")
        token = os.environ.get("KAIROS_DEV_TOKEN")
        if token:
            credentials[token] = os.environ.get("KAIROS_DEV_TENANT", "local-studio")
        if not isinstance(credentials, dict) or any(not isinstance(k, str) or len(k) < 24 or not isinstance(v, str) or not v for k, v in credentials.items()):
            raise ValueError("Developer credentials require tokens of at least 24 characters and nonempty tenant IDs.")
        origins = cors_origins()
        return cls(database_url=database_url, credentials=credentials, origins=origins)
