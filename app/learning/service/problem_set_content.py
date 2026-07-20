import hashlib
import json


MAX_EMBEDDING_TEXT_LENGTH = 1_500


def normalize_description(description: str | None) -> str:
    return (description or "").strip()


def build_problem_set_embedding_text(
    title: str,
    description: str | None,
    difficulty: str,
) -> str:
    parts = [f"문제세트 제목: {title.strip()}"]
    normalized_description = normalize_description(description)
    if normalized_description:
        parts.append(f"문제세트 설명: {normalized_description}")
    parts.append(f"난이도: {difficulty}")
    return "\n".join(parts)[:MAX_EMBEDDING_TEXT_LENGTH]


def calculate_content_hash(
    title: str,
    description: str | None,
    difficulty: str,
    problem_category_id: int,
    embedding_model: str,
    embedding_dimension: int,
) -> str:
    normalized = {
        "description": normalize_description(description),
        "difficulty": difficulty,
        "embeddingDimension": embedding_dimension,
        "embeddingModel": embedding_model,
        "problemCategoryId": problem_category_id,
        "title": title.strip(),
    }
    serialized = json.dumps(
        normalized,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()
