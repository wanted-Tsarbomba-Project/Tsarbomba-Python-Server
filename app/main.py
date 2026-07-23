import logging
import sys

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from app.chatbot.api.chat_router import router
from app.inquiry.router.inquiry_router import router as inquiry_router
from app.monitoring.api.monitoring_router import router as monitoring_router
from app.monitoring.http import HttpMetricsMiddleware
from app.problemset.routers.problem_set_draft_router import router as problem_set_draft_router
from app.opschat.api.opschat_router import router as opschat_router
from app.recommendation.api.recommendation_router import router as recommendation_router
from app.learning.api.learning_router import router as learning_router
from app.learning.repository.vector_store import learning_problem_set_vector_store

# 앱 로거(app.*)의 INFO 로그를 stdout으로 보냅니다.
# uvicorn은 자기 로거만 설정하므로, 별도 설정이 없으면 앱의 info 로그가 root(WARNING)에서 버려질 수 있습니다.
# Docker/Loki에서 trace_id 기반으로 요청 흐름을 추적하기 위해 명시적으로 설정합니다.
logging.basicConfig(
    level=logging.INFO,
    stream=sys.stdout,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)

app = FastAPI(
    title="Tsarbomba ChatBot API",
    description="데이터 분석 기반 LMS AI 챗봇 및 문제세트 초안 생성 서버",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8080"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# CORS까지 포함한 전체 요청/응답 사이클을 측정하기 위해 가장 바깥쪽 미들웨어로 추가합니다.
app.add_middleware(HttpMetricsMiddleware)

app.include_router(router)
app.include_router(opschat_router)
app.include_router(recommendation_router)
app.include_router(learning_router)
app.include_router(inquiry_router)
app.include_router(monitoring_router)
app.include_router(problem_set_draft_router)


@app.get("/health")
def health_check():
    index_status, problem_set_count = learning_problem_set_vector_store.health()
    return {
        "status": "ok",
        "learningIndexStatus": index_status,
        "learningProblemSets": problem_set_count,
    }


@app.get("/ready")
def readiness_check():
    index_status, problem_set_count = learning_problem_set_vector_store.health()
    if index_status != "ready" or problem_set_count < 1:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "status": "not_ready",
                "learningIndexStatus": index_status,
                "learningProblemSets": problem_set_count,
            },
        )
    return {
        "status": "ready",
        "learningIndexStatus": index_status,
        "learningProblemSets": problem_set_count,
    }