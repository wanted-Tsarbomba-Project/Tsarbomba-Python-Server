import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.lower() in {"true", "1", "yes", "y"}


def _env_csv(name: str, default: str) -> tuple[str, ...]:
    raw = os.getenv(name, default)
    return tuple(item.strip() for item in raw.split(",") if item.strip())


@dataclass(frozen=True)
class Settings:
    gemini_api_key: str
    gemini_model: str
    spring_base_url: str
    default_max_length: int
    dataset_sample_max_bytes: int
    allowed_dataset_url_hosts: tuple[str, ...]
    allow_local_dataset_path: bool
    safe_dataset_dir: str


def get_settings() -> Settings:
    return Settings(
        gemini_api_key=os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY", ""),
        gemini_model=os.getenv("GEMINI_MODEL", "gemini-3.5-flash"),
        spring_base_url=os.getenv("SPRING_BASE_URL", "http://localhost:8080"),
        default_max_length=_env_int("DEFAULT_MAX_LENGTH", 8000),
        dataset_sample_max_bytes=_env_int("DATASET_SAMPLE_MAX_BYTES", 102_400),
        allowed_dataset_url_hosts=_env_csv(
            "ALLOWED_DATASET_URL_HOSTS",
            "storage.googleapis.com,*.storage.googleapis.com",
        ),
        allow_local_dataset_path=_env_bool("ALLOW_LOCAL_DATASET_PATH", False),
        safe_dataset_dir=os.getenv("SAFE_DATASET_DIR", "/app/data"),
    )