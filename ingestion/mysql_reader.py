from typing import Any

from sqlalchemy import create_engine, text

from app.core.config import get_settings


MYSQL_URL_REQUIRED_MESSAGE = "MYSQL_URL is required to run problem-set ingestion"


def fetch_active_problem_sets() -> list[dict[str, Any]]:
    settings = get_settings()
    if not settings.mysql_url:
        raise RuntimeError(MYSQL_URL_REQUIRED_MESSAGE)

    engine = create_engine(settings.mysql_url, pool_pre_ping=True)
    query = text(
        """
        SELECT
            problem_set_id,
            category_id,
            title,
            description,
            difficulty,
            status
        FROM problem_set
        WHERE status = :active_status
          AND deleted_at IS NULL
        ORDER BY problem_set_id
        """
    )
    try:
        with engine.connect() as connection:
            rows = connection.execute(
                query,
                {"active_status": "ACTIVE"},
            ).mappings().all()
        return [dict(row) for row in rows]
    finally:
        engine.dispose()
