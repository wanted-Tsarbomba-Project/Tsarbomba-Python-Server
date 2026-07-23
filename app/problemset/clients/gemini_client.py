from typing import Any

from google import genai
from google.genai import types

from app.problemset.core.config import get_settings
from app.problemset.schemas.problem_set_draft_schema import (
    ChatMessage,
    ChatRequest,
    ProblemSetDraftEnvelope,
)
from app.problemset.services.dataset_analysis_service import infer_file_name
from app.problemset.tools.problem_set_tools import (
    analyze_dataset,
    get_problem_categories,
    get_problem_generation_policy,
    get_similar_problem_examples,
)
from app.problemset.utils.response_parser import parse_gemini_response


class ProblemSetGeminiClient:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.client = (
            genai.Client(api_key=self.settings.gemini_api_key)
            if self.settings.gemini_api_key
            else None
        )

    def generate(self, request: ChatRequest) -> tuple[str, dict[str, Any] | None, list[str]]:
        if self.client is None:
            return (
                "GEMINI_API_KEY 환경 변수가 설정되지 않아 Gemini를 호출할 수 없습니다.",
                None,
                [],
            )

        contents = _to_gemini_contents(request.history)
        contents.append(
            types.Content(
                role="user",
                parts=[types.Part.from_text(text=_build_user_prompt(request))],
            )
        )

        response = self.client.models.generate_content(
            model=self.settings.gemini_model,
            contents=contents,
            config=types.GenerateContentConfig(
                tools=[
                    analyze_dataset,
                    get_problem_categories,
                    get_problem_generation_policy,
                    get_similar_problem_examples,
                ],
                temperature=0.2,
                max_output_tokens=self.settings.default_max_length,
                response_mime_type="application/json",
                response_schema=ProblemSetDraftEnvelope,
                system_instruction=_build_system_instruction(request.operator_id),
            ),
        )

        answer, draft = parse_gemini_response(response)
        return answer, draft, _extract_used_tools(response)


def _build_system_instruction(operator_id: int) -> str:
    return f"""
너는 Code-Bomba LMS 문제세트 생성 도우미다.
현재 요청한 운영자 ID는 {operator_id}이다.

관리자가 주제, 난이도, 카테고리, 데이터셋을 주면 문제세트 등록 폼에 넣을 수 있는 초안을 만든다.

데이터셋 기반 문제가 필요하면 반드시 analyze_dataset 함수를 호출해 컬럼명, 샘플 값, 인코딩을 확인해야 한다.
카테고리 확인이 필요하면 get_problem_categories 함수를 호출한다.
문제 작성 규칙이 필요하면 get_problem_generation_policy 함수를 호출한다.
기존 문제 스타일 참고가 필요하면 get_similar_problem_examples 함수를 호출한다.

함수 결과에 없는 컬럼명, 데이터 값, 기존 문제 정보는 지어내지 않는다.
테스트 코드는 사용자의 제출 코드가 result 변수를 만든다고 가정하고 assert 문으로 작성한다.
CSV는 사용자가 os.environ["DATASET_PATH"]로 읽는다고 가정한다.
데이터셋 분석 결과에 cp949 또는 ms949 인코딩이 나오면 문제 본문과 힌트에 해당 encoding 옵션을 안내한다.
문제세트 초안은 관리자 검토용이며 최종 등록 전 사람이 확인해야 한다.

응답은 한국어 존댓말로 한다.
최종 답변은 반드시 JSON 객체 하나만 반환한다.
마크다운 코드블록은 사용하지 않는다.
각 필드는 짧고 명확하게 작성한다.
각 소문제의 testCases는 1개만 작성한다.
testCode는 가능하면 1~3개의 assert 문 중심으로 작성한다.
content, hint, explanation에는 긴 코드 예시를 넣지 않는다.
dataFileName, categoryName, difficulty는 요청 값을 그대로 유지한다.

응답 구조:
{{
  "answer": "관리자에게 보여줄 간단한 설명",
  "draft": {{
    "title": "...",
    "categoryName": "...",
    "difficulty": "EASY|MEDIUM|HARD",
    "description": "...",
    "dataFileName": "...",
    "problems": [
      {{
        "title": "...",
        "point": 1,
        "content": "...",
        "startCode": null,
        "hint": "...",
        "explanation": "...",
        "testCases": [
          {{
            "testCode": "assert ...",
            "isHidden": false,
            "timeoutMs": 3000
          }}
        ]
      }}
    ]
  }}
}}
""".strip()


def _build_user_prompt(request: ChatRequest) -> str:
    return f"""
관리자 요청:
{request.question}

문제세트 생성 조건:
- dataset_url: {request.dataset_url}
- data_file_name: {request.data_file_name or infer_file_name(request.dataset_url)}
- topic: {request.topic}
- category_name: {request.category_name}
- difficulty: {request.difficulty}
- problem_count: {request.problem_count}
- sub_problem_count: {request.sub_problem_count}

위 조건에 맞춰 Code-Bomba LMS 문제 등록 화면에 입력할 문제세트 초안 JSON을 만들어주세요.
""".strip()


def _to_gemini_contents(history: list[ChatMessage]) -> list[types.Content]:
    contents: list[types.Content] = []
    for message in history:
        role = "user" if message.role == "user" else "model"
        contents.append(
            types.Content(
                role=role,
                parts=[types.Part.from_text(text=message.content)],
            )
        )
    return contents


def _extract_used_tools(response: Any) -> list[str]:
    names: list[str] = []
    history = getattr(response, "automatic_function_calling_history", None) or []
    for content in history:
        for part in getattr(content, "parts", []) or []:
            function_call = getattr(part, "function_call", None)
            name = getattr(function_call, "name", None)
            if name:
                names.append(name)
    return list(dict.fromkeys(names))
