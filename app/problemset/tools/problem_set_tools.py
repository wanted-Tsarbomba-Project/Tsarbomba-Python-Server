from typing import Any

from clients.spring_client import spring_get
from services.dataset_analysis_service import analyze_csv_dataset


def analyze_dataset(dataset_url: str, data_file_name: str | None = None) -> dict[str, Any]:
    """
    Signed URL 또는 로컬 경로로 접근 가능한 CSV 데이터셋을 분석한다.

    관리자가 "이 데이터셋으로 문제를 만들어줘", "어떤 컬럼을 쓰면 좋을까",
    "난이도에 맞게 문제를 구성해줘"라고 요청할 때 사용한다.
    함수 결과의 컬럼명, 샘플 값, 숫자 후보 여부, 인코딩은 문제 생성에 반드시 참고해야 한다.
    """
    return analyze_csv_dataset(dataset_url, data_file_name)


def get_problem_categories() -> dict[str, Any]:
    """
    Spring 서버에서 현재 활성 문제 카테고리 목록을 조회한다.

    관리자가 카테고리를 지정하지 않았거나, 입력한 카테고리가 실제 존재하는지 확인해야 할 때 사용한다.
    문제세트 등록에는 활성 카테고리만 사용할 수 있다.
    """
    return spring_get("/api/v1/problem-categories")


def get_problem_generation_policy() -> dict[str, Any]:
    """
    Code-Bomba LMS 문제 등록 규칙을 조회한다.

    문제세트 title, description, difficulty, problems, testCases 구조와
    테스트 코드 작성 규칙을 확인할 때 사용한다.
    """
    return {
        "problem_set_schema": {
            "title": "문제세트 제목",
            "categoryName": "활성 카테고리 이름",
            "difficulty": "EASY | MEDIUM | HARD",
            "description": "문제세트 설명",
            "dataFileName": "CSV 파일명",
            "problems": [
                {
                    "title": "소문제 제목",
                    "point": 1,
                    "content": "학습자가 볼 문제 내용",
                    "startCode": None,
                    "hint": "힌트",
                    "explanation": "해설",
                    "testCases": [
                        {
                            "testCode": "assert result ...",
                            "isHidden": False,
                            "timeoutMs": 3000,
                        }
                    ],
                }
            ],
        },
        "rules": [
            "학습자는 os.environ['DATASET_PATH']로 CSV 경로를 읽는다고 가정한다.",
            "학습자는 pandas를 사용할 수 있다고 가정한다.",
            "문제는 result 변수에 정답을 담도록 요구한다.",
            "테스트 코드는 assert 문 중심으로 작성한다.",
            "CSV에 없는 컬럼명은 사용하지 않는다.",
            "기존 문제 예시는 스타일 참고용이며 그대로 복사하지 않는다.",
            "해설은 정답 방향과 핵심 pandas 연산을 설명한다.",
            "dataFileName, categoryName, difficulty는 요청값을 그대로 유지한다.",
        ],
    }


def get_similar_problem_examples(
    category_name: str | None = None,
    difficulty: str | None = None,
    topic: str | None = None,
) -> dict[str, Any]:
    """
    기존 문제세트 예시를 조회한다.

    비슷한 주제나 난이도의 문제 스타일을 참고하되,
    기존 문제를 그대로 복사하지 않도록 하기 위해 사용한다.
    1차 구현에서는 Spring 문제세트 목록 API를 사용하고,
    추후 ChromaDB 같은 벡터 DB 검색으로 교체할 수 있다.
    """
    params: dict[str, Any] = {
        "page": 0,
        "size": 5,
        "sort": "DEFAULT",
    }

    if difficulty:
        params["difficulty"] = difficulty

    category_id = _find_category_id_by_name(category_name) if category_name else None
    if category_id is not None:
        params["categoryId"] = category_id

    response = spring_get("/api/v1/problem-sets", params=params)
    response["search_hint"] = {
        "category_name": category_name,
        "difficulty": difficulty,
        "topic": topic,
        "note": "topic은 현재 Gemini가 결과 필터링 힌트로만 사용한다.",
    }
    return response


def _find_category_id_by_name(category_name: str | None) -> int | None:
    if not category_name:
        return None

    response = get_problem_categories()
    if "error" in response:
        return None

    for item in _walk_dicts(response):
        name = item.get("categoryName") or item.get("name") or item.get("title")
        category_id = item.get("categoryId") or item.get("id")
        if name == category_name and category_id is not None:
            try:
                return int(category_id)
            except (TypeError, ValueError):
                return None
    return None


def _walk_dicts(value: Any) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    if isinstance(value, dict):
        found.append(value)
        for child in value.values():
            found.extend(_walk_dicts(child))
    elif isinstance(value, list):
        for child in value:
            found.extend(_walk_dicts(child))
    return found
