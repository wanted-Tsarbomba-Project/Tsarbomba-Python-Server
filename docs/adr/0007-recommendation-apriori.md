# ADR-0007 — 문제집 추천: 브루트포스 연관규칙(Apriori), LMS DB 직접 read, 내부 배치 엔드포인트

> 상태: **accepted**
> 관련: [ARCHITECTURE §5](../ARCHITECTURE.md), [ADR-0008](0008-observability.md)

## 맥락

"이 문제집을 푼 사람은 저 문제집도 푼다"는 패턴으로 사용자별 문제집을 추천해야 한다. Spring이 직접 계산할 수도 있지만, 집합·조합 연산이 많아 파이썬이 낫다. 데이터를 어디서 읽고, 어떤 알고리즘으로, 어떤 인터페이스로 노출할지 정해야 했다.

## 결정

1. **알고리즘: 브루트포스 연관규칙(Apriori류).** 외부 ML 라이브러리 없이 표준 라이브러리(`itertools.combinations`)로 직접 구현(`service/apriori.py`). 응답의 `algorithm` = `"ASSOCIATION_RULE_BRUTE_FORCE"`.
2. **데이터: LMS MySQL을 직접 read**(`service/repository.py`, `pymysql`). Spring API 경유가 아니라 같은 DB를 조회한다.
3. **인터페이스: 내부 배치 엔드포인트** `POST /internal/recommendations/problem-sets/generate`. 요청/응답 **camelCase**(Pydantic alias). Spring이 트리거하고 결과 저장은 Spring이 한다(이 서버는 stateless 계산기).
4. DB 조회 실패는 `RecommendationRepositoryError` → 라우터에서 **HTTP 503**.

### 알고리즘 상세 (재현용)

- 상수: `MIN_SUPPORT_COUNT = 2`, `MAX_ITEMSET_SIZE = 4`.
- 입력: `completed_by_user: {user_id: {problem_set_id...}}`, `active_problem_set_ids: {…}`, `recommendation_count`.
- 단계:
  1. **트랜잭션 구성**: 각 사용자의 완료집합 ∩ 활성집합. 빈 트랜잭션 제외.
  2. **빈발 아이템셋**: 각 트랜잭션에서 크기 1..min(len, 4)의 조합 카운트 → `count ≥ 2`만 유지.
  3. **규칙 생성**: 크기 ≥ 2 아이템셋마다, 각 원소를 타깃으로 빼고 나머지를 antecedent로.
     - `support = itemset_count / 총트랜잭션수`
     - `confidence = itemset_count / antecedent_count`
     - `lift = confidence / (target_count/총트랜잭션수)` (분모 0이면 0.0). 각 값 `round(…, 6)`.
     - antecedent/target의 support_count가 없으면 스킵.
  4. **사용자별 추천**: 완료집합의 크기 1..min(len, 3) 조합을 antecedent로 매칭. 타깃이 **이미 완료** 또는 **비활성**이면 제외. 문제집당 최적 규칙 1개 유지.
     - **정렬키(내림차순)**: `(lift, confidence, support, len(antecedent))`. 상위 `recommendation_count`개. 후보가 적으면 있는 만큼만.
  - 결과: `{user_id: [ProblemSetRecommendation(problem_set_id, support, confidence, lift, rank_no)]}`. 추천 없는 사용자는 결과에서 제외.

### SQL 2종 (`repository.py`)

```sql
-- find_completed_problem_sets_by_user()  → {user_id: {problem_set_id...}}
SELECT pp.user_id, pp.problem_set_id
FROM problem_progress pp
JOIN problem_set ps      ON ps.problem_set_id = pp.problem_set_id
JOIN problem_category pc ON pc.category_id   = ps.category_id
WHERE pp.is_completed = true AND ps.status = 'ACTIVE' AND pc.status = 'ACTIVE';

-- find_active_problem_set_ids()  → {problem_set_id...}
SELECT problem_set_id
FROM problem_set ps
JOIN problem_category pc ON pc.category_id = ps.category_id
WHERE ps.status = 'ACTIVE' AND pc.status = 'ACTIVE';
```

- 연결: `pymysql.connect(host,port,user,password,database, charset="utf8mb4", cursorclass=DictCursor, connect_timeout=3, read_timeout=30, write_timeout=30)`. `with` 컨텍스트로 커넥션·커서 정리.

## 근거

- 문제집 수가 작아(활성 세트 기준) `MAX_ITEMSET_SIZE=4` 브루트포스가 실용적으로 충분하다. 외부 라이브러리 의존 없이 표준 라이브러리로 투명하게 구현한다.
- **DB 직접 read**: 추천은 대량 집계라 Spring REST로 사용자별 완료집합을 끌어오면 왕복이 폭발한다. 배치 성격이고 읽기 전용이라 같은 DB를 직접 조회하는 게 단순·빠르다.
- **내부 엔드포인트(`/internal`)**: 외부 노출용이 아니라 Spring 배치가 부르는 계산 API임을 경로로 표시.

## 비고

- ⚠️ **트레이드오프(결합)**: 이 서버가 LMS 스키마(`problem_progress`, `problem_set`, `problem_category` 테이블·컬럼)에 **직접 결합**된다. Spring이 스키마를 바꾸면 이 SQL이 깨진다. 배치·읽기전용이라 감수하되, 스키마 변경 시 양쪽을 같이 본다.
- 단계별 소요시간·규모를 메트릭/로그로 남긴다(`recommendation_python_generation_*`) → [ADR-0008](0008-observability.md). 이때만 `recommendation`이 `monitoring/metrics`를 import(도메인 경계의 유일한 예외적 공유).
- 응답이 camelCase인 건 chatbot(snake_case)과 다르다 — 호출 성격이 달라서다([ADR-0006](0006-spring-boundary-contract.md) 대비).
