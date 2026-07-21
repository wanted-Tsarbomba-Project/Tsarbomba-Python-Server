import logging
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.learning.schema.learning_recommendation import Difficulty


logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[3]


class VectorStoreUnavailableError(RuntimeError):
    """Raised when the local Chroma index cannot be used."""


class VectorStoreEmptyError(VectorStoreUnavailableError):
    """Raised when problem-set ingestion has not populated the index."""


@dataclass(frozen=True)
class SimilarProblemSet:
    problem_set_id: int
    title: str
    difficulty: Difficulty
    semantic_similarity: float


def resolve_chroma_path(configured_path: str) -> Path:
    path = Path(configured_path)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path.resolve()


class LearningProblemSetVectorStore:
    def __init__(self) -> None:
        self._collection: Any | None = None
        self._initialization_lock = threading.Lock()
        self._last_initialization_error: str | None = None

    def initialize(self) -> bool:
        if self._collection is not None:
            return True

        with self._initialization_lock:
            if self._collection is not None:
                return True
            try:
                import chromadb

                settings = get_settings()
                persist_path = resolve_chroma_path(
                    settings.chroma_persist_directory
                )
                client = chromadb.PersistentClient(path=str(persist_path))
                self._collection = client.get_or_create_collection(
                    name=settings.learning_problem_set_collection,
                    embedding_function=None,
                    metadata={"hnsw:space": "cosine"},
                )
                self._last_initialization_error = None
                logger.info(
                    "event=learning_vector_store_ready collection=%s",
                    settings.learning_problem_set_collection,
                )
                return True
            except Exception as exc:
                self._collection = None
                self._last_initialization_error = type(exc).__name__
                logger.warning(
                    "event=learning_vector_store_unavailable exception_type=%s",
                    type(exc).__name__,
                )
                return False

    def _require_collection(self) -> Any:
        if not self.initialize() or self._collection is None:
            raise VectorStoreUnavailableError("learning vector store is unavailable")
        return self._collection

    def count(self) -> int:
        try:
            return int(self._require_collection().count())
        except VectorStoreUnavailableError:
            raise
        except Exception as exc:
            logger.warning(
                "event=learning_vector_store_count_failed exception_type=%s",
                type(exc).__name__,
            )
            raise VectorStoreUnavailableError(
                "learning vector store count failed"
            ) from exc

    def health(self) -> tuple[str, int]:
        try:
            count = self.count()
            return ("ready", count) if count > 0 else ("degraded", 0)
        except VectorStoreUnavailableError:
            return "degraded", 0

    def search_similar(
        self,
        query_embedding: list[float],
        problem_category_id: int,
        result_count: int,
    ) -> list[SimilarProblemSet]:
        settings = get_settings()
        if len(query_embedding) != settings.gemini_embedding_dimension:
            raise ValueError("query embedding has an unexpected dimension")

        collection = self._require_collection()
        try:
            total_count = int(collection.count())
            if total_count == 0:
                raise VectorStoreEmptyError(
                    "learning problem-set ingestion is required"
                )
            n_results = min(max(1, result_count), total_count)
            result = collection.query(
                query_embeddings=[query_embedding],
                n_results=n_results,
                where={"problemCategoryId": problem_category_id},
                include=["metadatas", "distances"],
            )
        except VectorStoreEmptyError:
            raise
        except Exception as exc:
            logger.warning(
                "event=learning_vector_store_search_failed exception_type=%s",
                type(exc).__name__,
            )
            raise VectorStoreUnavailableError(
                "learning vector search failed"
            ) from exc

        metadatas = (result.get("metadatas") or [[]])[0]
        distances = (result.get("distances") or [[]])[0]
        if len(metadatas) != len(distances):
            raise VectorStoreUnavailableError(
                "learning vector search returned inconsistent results"
            )

        candidates: list[SimilarProblemSet] = []
        try:
            for metadata, distance in zip(metadatas, distances):
                semantic_similarity = max(0.0, min(1.0, 1.0 - float(distance)))
                candidates.append(
                    SimilarProblemSet(
                        problem_set_id=int(metadata["problemSetId"]),
                        title=str(metadata["title"]),
                        difficulty=Difficulty(str(metadata["difficulty"])),
                        semantic_similarity=semantic_similarity,
                    )
                )
        except (KeyError, TypeError, ValueError) as exc:
            raise VectorStoreUnavailableError(
                "learning vector search returned invalid metadata"
            ) from exc
        return candidates

    def get_all_metadata(self) -> dict[str, dict[str, Any]]:
        collection = self._require_collection()
        try:
            result = collection.get(include=["metadatas"])
            ids = result.get("ids") or []
            metadatas = result.get("metadatas") or []
            if len(ids) != len(metadatas):
                raise ValueError("inconsistent Chroma metadata result")
            return {
                str(record_id): dict(metadata or {})
                for record_id, metadata in zip(ids, metadatas)
            }
        except Exception as exc:
            logger.warning(
                "event=learning_vector_store_read_failed exception_type=%s",
                type(exc).__name__,
            )
            raise VectorStoreUnavailableError(
                "learning vector metadata read failed"
            ) from exc

    def upsert(
        self,
        ids: list[str],
        embeddings: list[list[float]],
        metadatas: list[dict[str, Any]],
    ) -> None:
        if not ids:
            return
        settings = get_settings()
        if not (len(ids) == len(embeddings) == len(metadatas)):
            raise ValueError("upsert record lengths must match")
        if any(
            len(embedding) != settings.gemini_embedding_dimension
            for embedding in embeddings
        ):
            raise ValueError("upsert embedding has an unexpected dimension")
        try:
            self._require_collection().upsert(
                ids=ids,
                embeddings=embeddings,
                metadatas=metadatas,
            )
        except Exception as exc:
            logger.warning(
                "event=learning_vector_store_upsert_failed record_count=%s exception_type=%s",
                len(ids),
                type(exc).__name__,
            )
            raise VectorStoreUnavailableError(
                "learning vector upsert failed"
            ) from exc

    def delete(self, ids: list[str]) -> None:
        if not ids:
            return
        try:
            self._require_collection().delete(ids=ids)
        except Exception as exc:
            logger.warning(
                "event=learning_vector_store_delete_failed record_count=%s exception_type=%s",
                len(ids),
                type(exc).__name__,
            )
            raise VectorStoreUnavailableError(
                "learning vector delete failed"
            ) from exc


learning_problem_set_vector_store = LearningProblemSetVectorStore()
