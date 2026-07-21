import logging
from dataclasses import dataclass
from typing import Any, TypeVar

from app.core.config import get_settings
from app.learning.repository.vector_store import (
    LearningProblemSetVectorStore,
    VectorStoreUnavailableError,
)
from app.learning.schema.learning_recommendation import Difficulty
from app.learning.service.gemini_embedding import GeminiEmbeddingError, embed_texts
from app.learning.service.problem_set_content import (
    build_problem_set_embedding_text,
    calculate_content_hash,
    normalize_description,
)
from ingestion.mysql_reader import (
    MYSQL_URL_REQUIRED_MESSAGE,
    fetch_active_problem_sets,
)


logger = logging.getLogger(__name__)
T = TypeVar("T")
EMPTY_PROBLEM_SET_RESULT_MESSAGE = (
    "No ACTIVE problem sets found; existing Chroma index was preserved"
)


class IngestionDataError(ValueError):
    """Raised before index mutation when a MySQL row is not safe to ingest."""


@dataclass(frozen=True)
class ProblemSetIndexRecord:
    problem_set_id: int
    problem_category_id: int
    title: str
    description: str
    difficulty: Difficulty
    content_hash: str

    def embedding_text(self) -> str:
        return build_problem_set_embedding_text(
            title=self.title,
            description=self.description,
            difficulty=self.difficulty.value,
        )

    def metadata(self) -> dict[str, Any]:
        settings = get_settings()
        return {
            "problemSetId": self.problem_set_id,
            "title": self.title,
            "difficulty": self.difficulty.value,
            "problemCategoryId": self.problem_category_id,
            "contentHash": self.content_hash,
            "embeddingModel": settings.gemini_embedding_model,
            "embeddingDimension": settings.gemini_embedding_dimension,
        }


def validate_problem_set_rows(
    rows: list[dict[str, Any]],
) -> list[ProblemSetIndexRecord]:
    settings = get_settings()
    records: list[ProblemSetIndexRecord] = []
    seen_ids: set[int] = set()

    for row in rows:
        try:
            problem_set_id = int(row["problem_set_id"])
            problem_category_id = int(row["category_id"])
            title_value = row["title"]
            title = title_value.strip() if isinstance(title_value, str) else ""
            description_value = row.get("description")
            if description_value is not None and not isinstance(description_value, str):
                raise IngestionDataError("description must be a string or null")
            description = normalize_description(description_value)
            difficulty = Difficulty(str(row["difficulty"]))
            status = str(row["status"])
        except (KeyError, TypeError, ValueError) as exc:
            raise IngestionDataError("invalid problem-set ingestion row") from exc

        if problem_set_id <= 0 or problem_category_id <= 0:
            raise IngestionDataError("problem-set and category IDs must be positive")
        if not title:
            raise IngestionDataError("problem-set title must not be blank")
        if status != "ACTIVE":
            raise IngestionDataError("ingestion row must be ACTIVE")
        if problem_set_id in seen_ids:
            raise IngestionDataError("duplicate problemSetId in ingestion result")
        seen_ids.add(problem_set_id)

        content_hash = calculate_content_hash(
            title=title,
            description=description,
            difficulty=difficulty.value,
            problem_category_id=problem_category_id,
            embedding_model=settings.gemini_embedding_model,
            embedding_dimension=settings.gemini_embedding_dimension,
        )
        records.append(
            ProblemSetIndexRecord(
                problem_set_id=problem_set_id,
                problem_category_id=problem_category_id,
                title=title,
                description=description,
                difficulty=difficulty,
                content_hash=content_hash,
            )
        )
    return records


def _batches(items: list[T], batch_size: int) -> list[list[T]]:
    if batch_size <= 0:
        raise ValueError("learning_embedding_batch_size must be positive")
    return [items[index : index + batch_size] for index in range(0, len(items), batch_size)]


def run_ingestion() -> dict[str, int]:
    settings = get_settings()
    rows = fetch_active_problem_sets()
    if not rows:
        raise RuntimeError(EMPTY_PROBLEM_SET_RESULT_MESSAGE)
    records = validate_problem_set_rows(rows)

    vector_store = LearningProblemSetVectorStore()
    if not vector_store.initialize():
        raise VectorStoreUnavailableError("learning vector store initialization failed")
    existing = vector_store.get_all_metadata()

    inserted_records: list[ProblemSetIndexRecord] = []
    updated_records: list[ProblemSetIndexRecord] = []
    unchanged_count = 0
    for record in records:
        existing_metadata = existing.get(str(record.problem_set_id))
        if existing_metadata is None:
            inserted_records.append(record)
        elif existing_metadata.get("contentHash") == record.content_hash:
            unchanged_count += 1
        else:
            updated_records.append(record)

    changed_records = inserted_records + updated_records
    embedding_by_id: dict[int, list[float]] = {}
    for batch in _batches(changed_records, settings.learning_embedding_batch_size):
        embeddings = embed_texts([record.embedding_text() for record in batch])
        if len(embeddings) != len(batch):
            raise GeminiEmbeddingError(
                "Gemini returned an unexpected ingestion embedding count"
            )
        embedding_by_id.update(
            {
                record.problem_set_id: embedding
                for record, embedding in zip(batch, embeddings)
            }
        )

    for batch in _batches(changed_records, settings.learning_embedding_batch_size):
        vector_store.upsert(
            ids=[str(record.problem_set_id) for record in batch],
            embeddings=[embedding_by_id[record.problem_set_id] for record in batch],
            metadatas=[record.metadata() for record in batch],
        )

    current_ids = {str(record.problem_set_id) for record in records}
    deleted_ids = sorted(set(existing) - current_ids)
    vector_store.delete(deleted_ids)

    result = {
        "total": len(records),
        "inserted": len(inserted_records),
        "updated": len(updated_records),
        "unchanged": unchanged_count,
        "deleted": len(deleted_ids),
    }
    logger.info(
        "event=problem_set_ingestion_completed total=%s inserted=%s updated=%s unchanged=%s deleted=%s",
        result["total"],
        result["inserted"],
        result["updated"],
        result["unchanged"],
        result["deleted"],
    )
    return result


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
    try:
        run_ingestion()
    except RuntimeError as exc:
        if str(exc) == MYSQL_URL_REQUIRED_MESSAGE:
            logger.error(
                "event=problem_set_ingestion_failed reason=mysql_url_missing message=%s",
                MYSQL_URL_REQUIRED_MESSAGE,
            )
        elif str(exc) == EMPTY_PROBLEM_SET_RESULT_MESSAGE:
            logger.error(
                "event=problem_set_ingestion_failed reason=no_active_problem_sets "
                "message=%s",
                EMPTY_PROBLEM_SET_RESULT_MESSAGE,
            )
        else:
            logger.error(
                "event=problem_set_ingestion_failed exception_type=%s",
                type(exc).__name__,
            )
        raise SystemExit(1) from None
    except Exception as exc:
        logger.error(
            "event=problem_set_ingestion_failed exception_type=%s",
            type(exc).__name__,
        )
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
