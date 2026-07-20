import logging
from functools import lru_cache

from google import genai
from google.genai import types

from app.core.config import get_settings


logger = logging.getLogger(__name__)


class GeminiEmbeddingError(RuntimeError):
    """Raised when Gemini cannot return a valid embedding collection."""


@lru_cache()
def _get_client() -> genai.Client:
    return genai.Client(api_key=get_settings().gemini_api_key)


def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        raise ValueError("at least one text is required")

    try:
        settings = get_settings()
        response = _get_client().models.embed_content(
            model=settings.gemini_embedding_model,
            contents=texts,
            config=types.EmbedContentConfig(
                task_type="SEMANTIC_SIMILARITY",
                output_dimensionality=settings.gemini_embedding_dimension,
            ),
        )
        embeddings = response.embeddings
        if not embeddings or len(embeddings) != len(texts):
            raise GeminiEmbeddingError(
                "Gemini returned an unexpected number of embeddings"
            )

        values: list[list[float]] = []
        for embedding in embeddings:
            if not embedding.values:
                raise GeminiEmbeddingError("Gemini returned an empty embedding")
            if len(embedding.values) != settings.gemini_embedding_dimension:
                raise GeminiEmbeddingError(
                    "Gemini returned an unexpected embedding dimension"
                )
            values.append(list(embedding.values))
        return values
    except GeminiEmbeddingError:
        logger.error(
            "event=learning_embedding_failed input_count=%s exception_type=%s",
            len(texts),
            GeminiEmbeddingError.__name__,
        )
        raise
    except Exception as exc:
        logger.error(
            "event=learning_embedding_failed input_count=%s exception_type=%s",
            len(texts),
            type(exc).__name__,
        )
        raise GeminiEmbeddingError("Gemini embedding request failed") from exc
