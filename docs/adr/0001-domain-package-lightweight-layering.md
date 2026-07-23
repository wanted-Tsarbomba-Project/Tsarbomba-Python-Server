# ADR-0001 — 도메인=최상위 패키지 + 경량 3계층 (풀세트 DDD 미채택)

> 상태: **accepted**
> 관련: [ADR-0002](0002-config-and-no-di.md)(DI 미채택), [ARCHITECTURE](../ARCHITECTURE.md)

## 맥락

원래 이 서버는 챗봇 하나만을 위한 평평한 구조(`app/{api,service,schema}`)였다. 이후 `monitoring`, `recommendation`이 다른 관심사로 추가되면서, **서로 코드를 안 건드리고** 작업할 경계가 필요해졌다.
동시에 Spring 백엔드의 `chatbot` 모듈은 풀세트 DDD(`presentation/application/domain/infrastructure` + port/adapter)를 쓴다. 이 FastAPI 서버도 그걸 따라갈지 결정해야 했다.

## 결정

1. **도메인을 최상위 패키지로 분리**한다: `app/chatbot/`, `app/recommendation/`, `app/monitoring/`. 공통 설정만 `app/core/`.
2. 각 도메인 내부는 **경량 3계층** `api/ · service/ · schema/` 만 둔다.
3. **풀세트 DDD 계층(entity/value-object/repository 인터페이스/application usecase·command·port)은 두지 않는다.**
4. 도메인 간 **직접 import 금지**. 공유는 `core/config.py`(설정)와 `monitoring/metrics.py`(메트릭 객체)뿐.
5. 새 도메인은 형제로 추가하고 `app/main.py`에서 `include_router` 한 줄로 연결한다.

## 근거

- 목표는 "도메인 분리(결합도↓)"지 "DDD 전술 패턴 풀세트"가 아니다. 팀원이 `monitoring`/`recommendation`을 `chatbot` 안 건드리고 붙이는 건 **패키지 경계**만으로 달성된다.
- 도메인이 형제로 나란히 있으면 "서로 import하면 안 된다"는 경계가 명확하고, `app/` 한 겹만 열면 도메인이 다 보인다(스크리밍 아키텍처).
- 파이썬은 동적 타입이라 계층을 늘리면 사람이 관리해야 한다(컴파일러가 안 잡아줌). FastAPI 공식 권장도 도메인별 `router/service/schema` 수준이다.
- 이 서버의 본질은 **외부 AI(Gemini) 호출·알고리즘 계산**이라 풍부한 도메인 모델로 키울 게 적다. 풀세트를 깔면 **빈 껍데기 계층**(엔티티 없는 domain/, 구현 하나뿐인 repository)만 늘어난다.
- Spring이 풀세트 DDD를 쓰는 건 틀린 게 아니다 — 거긴 규칙이 복잡하니 맞다. **파이썬/이 서버 규모에선 기본값이 아니다.**

## 비고

- 진짜 비즈니스 규칙이 복잡해질 때(정답 판정·재시도·점수 산정이 도메인 객체로 자랄 때) 계층 도입을 재검토한다.
- 실제 예외: `recommendation/service`는 파일이 3개(`apriori`·`recommendation_service`·`repository`)로 나뉘는데, 이는 계층이 아니라 **역할 분리**(알고리즘 / 오케스트레이션 / DB)다. 경량 계층 안에서의 자연스러운 분할.
