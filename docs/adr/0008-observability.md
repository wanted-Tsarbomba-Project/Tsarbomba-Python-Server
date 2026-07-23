# ADR-0008 — 관측: Prometheus 메트릭 + HTTP 미들웨어(카디널리티 억제) + 구조적 로깅 + trace 상관

> 상태: **accepted**
> 관련: [ADR-0006](0006-spring-boundary-contract.md)(X-Trace-Id), [ADR-0009](0009-deployment-topology.md)(promtail→Loki), [CONVENTION §6](../CONVENTION.md)

## 맥락

두 서비스(Spring·FastAPI)가 얽힌 요청을 추적하고, HTTP·추천 성능을 대시보드로 봐야 한다. 파이썬 로그가 유실되지 않게, 그리고 메트릭 라벨이 폭발하지 않게 설계해야 했다.

## 결정

### 1. 로깅 → stdout, 구조적, PII 미포함
- `app/main.py`가 `logging.basicConfig(level=INFO, stream=sys.stdout, format="%(asctime)s %(levelname)s [%(name)s] %(message)s")`로 앱 로거(`app.*`)를 stdout에 연결한다. (없으면 uvicorn이 자기 로거만 설정 → `logger.info`가 root(WARNING·핸들러 없음)에서 버려져 Loki에 안 남는다.)
- 로그는 `event=<이름> key=value` 한 줄 구조. 유저 입력 원문/AI 응답 본문은 남기지 않고 **길이만**.

### 2. Prometheus 메트릭 (`monitoring/metrics.py`, `/metrics`)
- `python_http_requests_total`(Counter), `python_http_request_duration_seconds`(Histogram) — 라벨 `domain, method, api, status`.
- `recommendation_python_generation_stage_duration_seconds`(Histogram) + `_last_duration_seconds`(Gauge) — 라벨 `stage, scale_users`.
- `recommendation_python_generation_scale`(Gauge) — 라벨 `type`.
- 노출: `GET /metrics`(`generate_latest`, `include_in_schema=False`).

### 3. HTTP 미들웨어 — 카디널리티 억제 (`monitoring/http.py`)
- `HttpMetricsMiddleware`가 모든 요청의 수·소요시간을 기록. **가장 바깥 미들웨어**(CORS 포함 전 사이클 측정)로 등록.
- `api` 라벨은 **실제 path가 아니라 라우트 템플릿**(`request.scope["route"].path`)을 쓴다 → path param 값이 라벨을 폭발시키지 않게.
- `domain` 라벨은 path prefix로 분류: `/internal/recommendations`→`recommendation`, `/chat`→`chatbot`, 그 외→`system`.
- `/metrics`는 측정 제외(`_EXCLUDED_PATHS`).

### 4. trace 상관
- Spring `X-Trace-Id` → 로그 `trace_id=`. 값으로 매칭해 Loki에서 BE(`traceId=`)+FastAPI(`trace_id=`) 로그를 한 화면에 조회.

## 근거

- stdout 로깅은 컨테이너 표준이다(promtail이 파일을 tail → Loki). basicConfig 한 줄이 유실 문제를 막는다.
- **라우트 템플릿 라벨**은 Prometheus 카디널리티 폭발(모든 `roomId`가 별 시계열)을 막는 정석이다.
- 추천을 `stage`별로 쪼개 재면(db_fetch/algorithm/response_build/total, `scale_users`별) 규모에 따른 병목을 본다.

## 비고

- `recommendation`이 `monitoring/metrics`를 import하는 것이 도메인 경계의 유일한 예외적 공유 → [ADR-0001](0001-domain-package-lightweight-layering.md).
- 로그 수집 파이프라인(promtail·Loki 라벨 통일 `job=chatbot`)은 [ADR-0009](0009-deployment-topology.md).
- trace 상관 계약(헤더명·PII 규칙)은 [ADR-0006](0006-spring-boundary-contract.md)과 짝.
