import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    gemini_api_key: str
    gemini_model: str
    spring_base_url: str
    default_max_length: int


def get_settings() -> Settings:
    return Settings(
        gemini_api_key=os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY", ""),
        gemini_model=os.getenv("GEMINI_MODEL", "gemini-3.5-flash"),
        spring_base_url=os.getenv("SPRING_BASE_URL", "http://localhost:8080"),
        default_max_length=_env_int("DEFAULT_MAX_LENGTH", 8000),
    )
