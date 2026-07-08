import logging
import sys

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.chatbot.api.chat_router import router
from app.monitoring.api.monitoring_router import router as monitoring_router
from app.monitoring.http import HttpMetricsMiddleware
from app.recommendation.api.recommendation_router import router as recommendation_router

# 앱 로거(app.*)의 INFO 로그를 stdout 으로 흘린다.
# uvicorn 은 자기 로거만 설정해서, 이게 없으면 logger.info(chatbot_chat_started 등)가
# root(WARNING·핸들러 없음)에서 전부 버려진다 → docker/Loki 에 안 남고 trace_id 추적 불가.
logging.basicConfig(
    level=logging.INFO,
    stream=sys.stdout,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)

app = FastAPI(
    title="tsarbomba ChatBot API",
    description="데이터 분석 튜터링 AI 챗봇 서버",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8080"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# CORS까지 포함한 전체 요청/응답 사이클을 측정하기 위해 가장 바깥쪽 미들웨어로 추가한다.
app.add_middleware(HttpMetricsMiddleware)

app.include_router(router)
app.include_router(recommendation_router)
app.include_router(monitoring_router)


@app.get("/health")
def health_check():
    return {"status": "ok"}
