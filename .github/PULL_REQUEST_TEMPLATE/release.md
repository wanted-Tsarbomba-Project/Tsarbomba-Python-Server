# 🚀 Python AI Server Release Pull Request

> PR 제목은 `[Release] vX.Y.Z` 형식으로 작성해주세요.
>
> 예시: `[Release] v1.2.0`
>
> 이 저장소는 `develop → main` 머지 후 배포 workflow가 실행됩니다. 현재 Git tag와 GitHub Release는 자동 생성되지 않으므로, 필요한 경우 배포 확인 후 `main` 기준으로 직접 생성합니다.

## 📌 릴리즈 정보

| 항목 | 내용 |
|------|------|
| **버전** | `v0.0.0 → v0.0.0` |
| **릴리즈 날짜** | YYYY-MM-DD |
| **기준 브랜치** | `develop` |
| **병합 브랜치** | `main` |
| **배포 환경** | `FastAPI / EC2 / Docker Compose / ECR / SSM / RDS / ChromaDB / Gemini` |

---

# 📖 릴리즈 요약

> 이번 릴리즈의 주요 변경사항을 2~4개로 요약해주세요.

-
-
-

---

# 📋 릴리즈 노트

## Chatbot / OpsChat

### Added

-

### Changed

-

### Fixed

-

---

## Learning / Recommendation / Inquiry

### Added

-

### Changed

-

### Fixed

-

---

## Embedding / ChromaDB / Ingestion

### Added

-

### Changed

-

### Fixed

-

---

## Monitoring / Deploy

### Added

-

### Changed

-

### Fixed

-

---

# 🔌 API / 연동 계약 변경

## FastAPI 변경

- [ ] 없음
- [ ] 있음

| 구분 | Method | URL | 변경 내용 | 호출자 영향 |
|------|--------|-----|----------|------------|
| 추가 | `POST` | `/internal/...` |  | Spring / 없음 |
| 변경 | `POST` | `/internal/...` |  | Spring / 없음 |
| 삭제 | `DELETE` | `/internal/...` |  | Spring / 없음 |

## Spring 연동 계약

- [ ] 요청 JSON 필드와 타입을 확인했습니다.
- [ ] 응답 JSON 필드와 타입을 확인했습니다.
- [ ] HTTP 상태 코드와 timeout 동작을 확인했습니다.
- [ ] 기존 Spring fallback 동작에 영향을 주지 않습니다.
- [ ] 계약 변경이 있다면 Spring 담당자에게 공유했습니다.

변경 내용:

-

---

# 🧠 Gemini / Embedding 변경

- [ ] 없음
- [ ] 있음

| 항목 | 기존 | 변경 | 운영 영향 |
|------|------|------|----------|
| 생성 모델 |  |  | 추천 문구 / 챗봇 |
| 임베딩 모델 |  |  | 재색인 필요 / 없음 |
| 임베딩 차원 |  |  | 새 컬렉션 필요 / 없음 |
| timeout |  |  | Spring timeout 확인 / 없음 |

> 임베딩 모델 또는 차원이 바뀌면 기존 벡터와 혼용하지 않고 새 Chroma 컬렉션을 사용하며 전체 ingestion 여부를 확인합니다.

---

# 🗂️ ChromaDB / Ingestion 변경

- [ ] 없음
- [ ] 있음

| 확인 항목 | 내용 |
|----------|------|
| 컬렉션 이름 |  |
| 임베딩 차원 |  |
| 전체 재색인 필요 여부 | 필요 / 불필요 |
| MySQL 조회 조건 변경 |  |
| metadata / contentHash 변경 |  |
| 삭제 동기화 정책 변경 |  |

확인 사항:

- [ ] MySQL 조회 결과가 0건이면 기존 Chroma 색인을 보존합니다.
- [ ] 신규·변경 데이터만 필요한 경우 재임베딩합니다.
- [ ] INACTIVE 또는 삭제된 데이터의 동기화 정책을 확인했습니다.
- [ ] Chroma persistent directory와 Docker named volume 연결을 확인했습니다.
- [ ] ingestion 성공 후 `/ready`에서 색인 건수가 1개 이상인지 확인했습니다.

---

# 🔐 환경변수 / Secrets 변경

- [ ] 없음
- [ ] 있음

| 키 이름 | 구분 | 반영 위치 | 변경 내용 |
|---------|------|----------|----------|
| `KEY_NAME` | Secret / Variable | GitHub / EC2 `.env` | 추가 / 변경 / 삭제 |

운영 반영 필요 여부:

- [ ] 없음
- [ ] GitHub Secrets 변경 필요
- [ ] GitHub Variables 변경 필요
- [ ] EC2 `.env` 변경 필요
- [ ] SSM / IAM / Security Group 변경 필요

> API Key, DB 비밀번호, 토큰 등 실제 Secret 값은 PR 본문과 로그에 작성하지 않습니다.

---

# 🧪 릴리즈 체크리스트

- [ ] `develop` 브랜치의 최신 코드가 반영되었습니다.
- [ ] `develop → main` 방향의 Release PR입니다.
- [ ] `python -m pytest`가 통과했습니다.
- [ ] `/docs`와 `/openapi.json`에서 API 계약을 확인했습니다.
- [ ] 주요 API의 정상·실패·fallback 동작을 확인했습니다.
- [ ] `Dockerfile` 이미지 빌드를 확인했습니다.
- [ ] `requirements.txt` 의존성 추가·변경 여부를 확인했습니다.
- [ ] 운영 환경변수와 GitHub Secrets/Variables를 확인했습니다.
- [ ] Secret 값이 코드, 로그, PR 본문에 노출되지 않았습니다.
- [ ] ChromaDB 컬렉션·모델·차원 호환성을 확인했습니다.
- [ ] ingestion 실패 시 새 컨테이너 반영이 중단되는지 확인했습니다.
- [ ] 기존 Python 컨테이너가 ingestion 중 계속 서비스되는지 확인했습니다.
- [ ] `/health`와 `/ready`의 용도를 구분해 확인했습니다.
- [ ] Docker named volume의 Chroma 영속화를 확인했습니다.
- [ ] Merge Conflict가 없습니다.
- [ ] 릴리즈 노트를 작성했습니다.

---

# 🏷️ 버전 정보

| 이전 버전 | 변경 버전 | 버전 변경 유형 |
|----------|----------|----------------|
| `v0.0.0` | `v0.0.0` | `MAJOR` / `MINOR` / `PATCH` |

### 버전 변경 기준

- **MAJOR**: Spring 요청·응답 계약 변경, 기존 API 삭제, Chroma 데이터 호환성이 깨지는 변경
- **MINOR**: 새로운 FastAPI 기능·endpoint·추천 또는 RAG 기능 추가
- **PATCH**: 오류 처리, fallback, 프롬프트, 배포·ingestion 설정 보완

버전 변경 사유:

-

---

# 🚢 배포 흐름 확인

```text
develop → main 머지
→ Python Docker 이미지 빌드 및 ECR push
→ 기존 Python 컨테이너가 서비스를 유지한 상태에서 일회성 ingestion 실행
→ MySQL ACTIVE 데이터와 ChromaDB 동기화
→ ingestion 성공 시 새 Python 컨테이너 반영
→ /ready에서 Chroma 상태와 색인 건수 확인
→ ingestion 실패 시 새 버전 반영 중단
```

- [ ] ECR 이미지 push가 성공했습니다.
- [ ] SSM 배포 명령이 성공했습니다.
- [ ] ingestion이 성공했습니다.
- [ ] 새 Python 컨테이너가 정상 기동했습니다.
- [ ] `/ready`가 HTTP 200을 반환했습니다.

---

# 📦 Git Tag

> Tag가 필요하면 Release PR이 `main`에 머지되고 배포 검증이 끝난 후, 최신 `main` HEAD에 생성합니다.

```bash
git checkout main
git pull origin main

git tag v0.0.0
git push origin v0.0.0
```

---

# ✅ 배포 후 검증

```bash
curl http://<PYTHON_HOST>:8000/health
curl http://<PYTHON_HOST>:8000/ready
```

- [ ] `/health`의 `status`가 정상입니다.
- [ ] `/ready`의 `learningIndexStatus`가 `ready`입니다.
- [ ] `/ready`의 `learningProblemSets`가 1개 이상입니다.
- [ ] Swagger에서 변경된 endpoint를 확인했습니다.
- [ ] Spring에서 Python 내부 API 호출이 성공합니다.
- [ ] Gemini 장애 시 정해진 fallback이 동작합니다.
- [ ] EC2 Docker 컨테이너 로그에 Secret이 노출되지 않았습니다.

---

# 💬 기타 사항

> 리뷰어나 배포 담당자가 확인해야 할 사항을 작성해주세요.

-
