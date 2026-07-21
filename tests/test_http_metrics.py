from fastapi.testclient import TestClient

from app import main as main_module
from app.monitoring.metrics import HTTP_REQUESTS_TOTAL
from app.recommendation.api import recommendation_router
from app.recommendation.service.repository import RecommendationRepositoryError

client = TestClient(main_module.app)


def _count(domain: str, method: str, api: str, status: str) -> float:
    return HTTP_REQUESTS_TOTAL.labels(domain=domain, method=method, api=api, status=status)._value.get()


def test_health_check_is_labeled_as_system():
    before = _count("system", "GET", "/health", "200")
    response = client.get("/health")
    assert response.status_code == 200
    assert _count("system", "GET", "/health", "200") == before + 1


def test_readiness_returns_503_when_learning_index_is_empty(monkeypatch):
    monkeypatch.setattr(
        main_module.learning_problem_set_vector_store,
        "health",
        lambda: ("degraded", 0),
    )

    response = client.get("/ready")

    assert response.status_code == 503
    assert response.json()["detail"]["learningProblemSets"] == 0


def test_readiness_returns_200_when_learning_index_has_records(monkeypatch):
    monkeypatch.setattr(
        main_module.learning_problem_set_vector_store,
        "health",
        lambda: ("ready", 30),
    )

    response = client.get("/ready")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "learningIndexStatus": "ready",
        "learningProblemSets": 30,
    }


def test_recommendation_5xx_is_labeled_as_recommendation_domain(monkeypatch):
    # RDS 연결 실패 시나리오 재현: repository 계층에서 RecommendationRepositoryError가
    # 나면 503으로 응답하고, 그 5xx가 domain=recommendation으로 집계돼야 한다.
    def _raise(*args, **kwargs):
        raise RecommendationRepositoryError("RDS 연결 실패")

    monkeypatch.setattr(recommendation_router, "generate_problem_set_recommendations", _raise)

    before = _count("recommendation", "POST", "/internal/recommendations/problem-sets/generate", "503")
    response = client.post(
        "/internal/recommendations/problem-sets/generate",
        json={"recommendationCount": 3},
    )
    assert response.status_code == 503
    assert (
        _count("recommendation", "POST", "/internal/recommendations/problem-sets/generate", "503")
        == before + 1
    )


def test_metrics_endpoint_is_not_self_tracked():
    response = client.get("/metrics")
    assert response.status_code == 200
    assert b"python_http_requests_total" in response.content
