# Problem Set Generation RAG

Code-Bomba LMS의 문제세트 AI 초안 생성용 FastAPI 서버입니다.

이 서버는 실제 문제세트를 DB에 저장하지 않습니다. 관리자가 데이터셋과 생성 방향을 입력하면 Gemini Function Calling으로 데이터셋을 분석하고, 문제 등록 화면에 채워 넣을 수 있는 초안 JSON을 반환합니다.

## 구조

| 경로 | 역할 |
| --- | --- |
| `main.py` | FastAPI 앱 진입점 |
| `function_calling_problem_set_generation.py` | 기존 실행 명령을 위한 호환용 진입점 |
| `routers/` | HTTP API 라우터 |
| `services/` | 문제세트 초안 생성 흐름과 데이터셋 분석 로직 |
| `clients/` | Gemini, Spring 서버 호출 코드 |
| `tools/` | Gemini Function Calling에 등록되는 도구 함수 |
| `schemas/` | 요청/응답 Pydantic 모델 |
| `core/` | 환경 변수 설정 |
| `utils/` | Gemini 응답 파싱 보조 함수 |

## 환경 변수

| 이름 | 예시 | 설명 |
| --- | --- | --- |
| `GEMINI_API_KEY` | `your-gemini-api-key` | Gemini API Key |
| `GEMINI_MODEL` | `gemini-3.5-flash` | 사용할 Gemini 모델 |
| `DEFAULT_MAX_LENGTH` | `8000` | Gemini 응답 최대 토큰 수 |
| `SPRING_BASE_URL` | `http://localhost:8080` | Spring 서버 주소 |

## 실행

PowerShell 기준입니다.

```powershell
cd src/main/java/com/wanted/codebombalms/problems/rag/python
pip install -r requirements.txt

$env:GEMINI_API_KEY="your-gemini-api-key"
$env:GEMINI_MODEL="gemini-3.5-flash"
$env:DEFAULT_MAX_LENGTH="8000"
$env:SPRING_BASE_URL="http://localhost:8080"

uvicorn main:app --reload --port 8000
```

기존 파일명으로도 실행할 수 있습니다.

```powershell
uvicorn function_calling_problem_set_generation:app --reload --port 8000
```

## 요청 예시

```http
POST http://localhost:8000/problem-set-draft/chat
Content-Type: application/json
```

```json
{
  "question": "이 CSV 데이터셋으로 pandas 기초 문제세트를 만들어줘. 소문제는 3개 이상으로 구성해줘.",
  "operator_id": 1,
  "dataset_url": "C:/Users/user/Downloads/SW기술자_평균임금_20260712223319.csv",
  "data_file_name": "SW기술자_평균임금_20260712223319.csv",
  "topic": "SW기술자 평균임금 분석",
  "category_name": "공공 데이터",
  "difficulty": "EASY",
  "problem_count": 1,
  "sub_problem_count": 3,
  "history": []
}
```

Spring 서버에서 호출할 때는 `dataset_url`에 GCS Signed URL을 전달합니다. 직접 테스트할 때는 로컬 CSV 경로도 사용할 수 있습니다.

## 응답 예시

```json
{
  "answer": "SW기술자 평균임금 데이터셋을 활용하여 EASY 난이도의 문제세트 초안을 생성했습니다.",
  "draft": {
    "title": "SW기술자 평균임금 분석 기초",
    "categoryName": "공공 데이터",
    "difficulty": "EASY",
    "description": "SW기술자의 등급별 조사인원과 평균임금 데이터를 활용합니다.",
    "dataFileName": "SW기술자_평균임금_20260712223319.csv",
    "problems": [
      {
        "title": "최고 평균임금 기술 등급 찾기",
        "point": 30,
        "content": "평균임금이 가장 높은 기술 등급의 구분 값을 result 변수에 저장하세요.",
        "startCode": null,
        "hint": "idxmax()와 loc를 함께 사용할 수 있습니다.",
        "explanation": "최댓값이 있는 행의 인덱스를 찾고 해당 행의 구분 값을 가져옵니다.",
        "testCases": [
          {
            "testCode": "assert result == expected",
            "isHidden": false,
            "timeoutMs": 3000
          }
        ]
      }
    ]
  },
  "used_tools": [
    "analyze_dataset",
    "get_problem_generation_policy"
  ]
}
```

## Function Calling 도구

| 함수 | 역할 |
| --- | --- |
| `analyze_dataset` | CSV 컬럼명, 샘플 값, 숫자 후보 여부, 인코딩 분석 |
| `get_problem_categories` | Spring 서버에서 활성 문제 카테고리 조회 |
| `get_problem_generation_policy` | 문제 등록 JSON 구조와 테스트 코드 작성 규칙 제공 |
| `get_similar_problem_examples` | 기존 문제세트 목록 조회 후 스타일 참고 |

## 설계 원칙

- LLM은 함수를 직접 실행하지 않고 어떤 도구가 필요한지만 선택합니다.
- 실제 도구 실행은 FastAPI 서버가 담당합니다.
- 데이터셋에 없는 컬럼명이나 값은 생성 결과에 사용하지 않습니다.
- 생성된 문제세트는 초안이며, 관리자가 검토한 뒤 기존 문제 등록 API로 최종 저장합니다.
- `get_similar_problem_examples`는 현재 Spring 목록 API 기반이며, 추후 ChromaDB 검색으로 교체할 수 있습니다.
