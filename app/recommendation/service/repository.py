import logging
from collections import defaultdict

import pymysql

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class RecommendationRepositoryError(RuntimeError):
    """Raised when recommendation source data cannot be loaded."""


def _get_connection():
    settings = get_settings()

    return pymysql.connect(
        host=settings.db_host,
        port=settings.db_port,
        user=settings.db_username,
        password=settings.db_password,
        database=settings.db_name,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        connect_timeout=3,
        read_timeout=30,
        write_timeout=30,
    )


def find_completed_problem_sets_by_user() -> dict[int, set[int]]:
    sql = """
        SELECT
            pp.user_id,
            pp.problem_set_id
        FROM problem_progress pp
        JOIN problem_set ps
            ON ps.problem_set_id = pp.problem_set_id
        JOIN problem_category pc
            ON pc.category_id = ps.category_id
        WHERE pp.is_completed = true
          AND ps.status = 'ACTIVE'
          AND pc.status = 'ACTIVE'
    """

    completed_by_user = defaultdict(set)

    try:
        with _get_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(sql)
                rows = cursor.fetchall()
    except pymysql.MySQLError as exc:
        logger.exception("완료 문제집 조회 중 DB 예외")
        raise RecommendationRepositoryError("추천 데이터 조회에 실패했습니다.") from exc

    for row in rows:
        completed_by_user[int(row["user_id"])].add(int(row["problem_set_id"]))

    return dict(completed_by_user)


def find_active_problem_set_ids() -> set[int]:
    sql = """
        SELECT problem_set_id
        FROM problem_set ps
        JOIN problem_category pc
            ON pc.category_id = ps.category_id
        WHERE ps.status = 'ACTIVE'
          AND pc.status = 'ACTIVE'
    """

    try:
        with _get_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(sql)
                rows = cursor.fetchall()
    except pymysql.MySQLError as exc:
        logger.exception("활성 문제집 조회 중 DB 예외")
        raise RecommendationRepositoryError("추천 데이터 조회에 실패했습니다.") from exc

    return {int(row["problem_set_id"]) for row in rows}
