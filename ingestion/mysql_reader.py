from typing import Any

from sqlalchemy import URL, create_engine, text

from app.core.config import get_settings


MYSQL_URL_REQUIRED_MESSAGE = (
    "MYSQL_URL or complete DB_* settings are required to run problem-set ingestion"
)


def build_mysql_connection_url() -> str | URL:
    settings = get_settings()
    if settings.mysql_url:
        return settings.mysql_url

    if not all(
        (
            settings.db_host,
            settings.db_name,
            settings.db_username,
            settings.db_password,
        )
    ):
        raise RuntimeError(MYSQL_URL_REQUIRED_MESSAGE)

    return URL.create(
        drivername="mysql+pymysql",
        username=settings.db_username,
        password=settings.db_password,
        host=settings.db_host,
        port=settings.db_port,
        database=settings.db_name,
    )


def fetch_active_problem_sets() -> list[dict[str, Any]]:
    engine = create_engine(build_mysql_connection_url(), pool_pre_ping=True)
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
