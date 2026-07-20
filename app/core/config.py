import re
from functools import lru_cache

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    gemini_api_key: str
    gemini_model: str = "gemini-3.5-flash"
    default_max_length: int = 3000
    db_host: str = "localhost"
    db_port: int = 3306
    db_name: str = ""
    db_username: str = ""
    db_password: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )

    @model_validator(mode="after")
    def validate_learning_collection_name(self) -> "Settings":
        model_slug = re.sub(
            r"[^a-zA-Z0-9]+",
            "_",
            self.gemini_embedding_model,
        ).strip("_").lower()
        expected_collection = (
            f"learning_problem_sets_{model_slug}_{self.gemini_embedding_dimension}"
        )
        if self.learning_problem_set_collection != expected_collection:
            raise ValueError(
                "learning_problem_set_collection must match the configured "
                "Gemini embedding model and dimension"
            )
        return self


@lru_cache()
def get_settings() -> Settings:
    return Settings()
