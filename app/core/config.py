import re
from functools import lru_cache

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    gemini_api_key: str
    gemini_model: str = "gemini-3.5-flash"
    gemini_reason_model: str = "gemini-3.5-flash"
    gemini_embedding_model: str = "gemini-embedding-001"
    gemini_embedding_dimension: int = Field(default=3072, gt=0)
    learning_reason_timeout_ms: int = Field(default=10000, gt=0)
    learning_embedding_timeout_ms: int = Field(default=10000, gt=0)
    mysql_url: str | None = None
    chroma_persist_directory: str = Field(
        default=".chroma/learning",
        min_length=1,
    )
    learning_problem_set_collection: str = Field(
        default="learning_problem_sets_gemini_embedding_001_3072",
        min_length=1,
    )
    learning_vector_candidate_count: int = Field(default=50, gt=0)
    learning_embedding_batch_size: int = Field(default=50, gt=0)
    default_max_length: int = 3000
    db_host: str = "localhost"
    db_port: int = 3306
    db_name: str = ""
    db_username: str = ""
    db_password: str = ""
    # opschat 도구 → Spring 내부 API (/internal/ops/*) 호출용
    spring_base_url: str = "http://localhost:8080"
    internal_api_token: str = ""

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
