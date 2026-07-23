# ADR-0009 — 배포 토폴로지: Docker→ECR→EC2 compose(+promtail 사이드카)→Loki, OIDC/SSM

> 상태: **accepted**
> 관련: [ADR-0008](0008-observability.md)(관측), [ADR-0002](0002-config-and-no-di.md)(설정 주입)

## 맥락

이 서버(④ 파이썬 박스)를 Spring 백엔드(②)·모니터링(③)과 함께 AWS에 배포해야 한다. 시크릿을 안전하게 주입하고, 로그를 Spring과 같은 곳에 모으고, 무중단에 가깝게 갱신해야 한다.

## 결정

### 1. 컨테이너 & 이미지
- `Dockerfile`: `python:3.12-slim` → `requirements.txt` 설치 → `app/`·`templates/` 복사 → `uvicorn app.main:app --host 0.0.0.0 --port 8000`.
- 이미지는 **ECR**(`team05/python:latest` + `:<git sha>`)에 푸시.

### 2. EC2 스택 (`deploy/docker-compose.yml`)
- 서비스 2개: `chatbot`(앱, `:8000`) + `promtail`(로그 사이드카).
- `chatbot`: `env_file: .env`(EC2에만 존재), `restart: unless-stopped`, json-file 로깅(`max-size 10m`, `max-file 3`).
- `promtail`: `grafana/promtail:3.0.0`, 도커 컨테이너 로그를 tail → **③ 모니터링 EC2의 Loki**(사설 IP)로 push.

### 3. 로그 라벨 통일 (`deploy/promtail-config.yml`)
- 컨테이너 로그에 `job=chatbot`, `host=chatbot-ec2`, `container=<이름>` 라벨.
- **Spring(job=lms)과 라벨 체계를 통일** → `{job=~"lms|chatbot"} |= "<traceId>"` 로 양쪽 로그 통합 조회 → [ADR-0008](0008-observability.md).

### 4. CI/CD (`.github/workflows/deploy.yml`)
- 트리거: `main` push / 수동. 동시 배포 방지(concurrency).
- **키리스**: GitHub OIDC로 AWS 역할 assume(`team05-github-actions`) — 장기 키 없음.
- 흐름: 이미지 빌드·ECR 푸시 → `.env` 조립(Secrets/Variables→파일, 값 마스킹) → 배포자산+`.env` **S3 업로드(SSE AES256)** → **SSM send-command**로 EC2에서 `aws s3 sync` → `docker compose pull && up -d` → `/health` 폴링(최대 60s) → `docker image prune`.
- **시크릿은 S3의 `.env`에만** 존재(SSM 명령에 시크릿을 싣지 않음).

## 근거

- OIDC+SSM: EC2에 SSH 키·장기 AWS 키를 두지 않고 배포한다(공격면↓). 시크릿은 S3(SSE) 경유로만 EC2에 도달.
- promtail 사이드카 + 라벨 통일: 앱 코드 변경 없이 컨테이너 로그를 Spring과 같은 Loki로 모아 통합 추적.
- `/health` 폴링으로 기동 실패를 배포 단계에서 잡는다(실패 시 로그 tail 후 종료).

## 비고

- ⚠️ promtail의 Loki 타깃은 ③ 모니터링 EC2의 **사설 IP**다. ③를 terminate 후 재생성하면 `promtail-config.yml`의 IP를 갱신해야 한다.
- `EC2_NAME_TAG`(`team05-01-python`)가 실제 인스턴스 Name 태그와 일치해야 SSM 대상이 잡힌다.
- 로컬 실행은 `.env` + `uvicorn app.main:app --reload --port 8000`. 설정 주입 규칙은 [ADR-0002](0002-config-and-no-di.md).
