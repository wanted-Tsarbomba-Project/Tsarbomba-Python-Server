"""
추천 질문 군집(union-find) 순수함수 격리 테스트.
LLM·임베딩 API 없이 '가짜 벡터'만 넣어 군집 규칙(τ=0.80, 크기≥2, 빈도순)을 검증한다.
"""
from app.suggested_questions.service.clustering import (
    MIN_CLUSTER_SIZE,
    SIMILARITY_THRESHOLD,
    cluster_questions,
)


def test_similar_questions_group_and_singleton_is_dropped():
    """같은 방향 벡터 2개는 한 클러스터, 직교한 1개(크기1)는 노이즈로 버려진다."""
    questions = ["튜플 만드는 법", "튜플 어떻게 만들어", "재귀가 뭐야"]
    embeddings = [[1.0, 0.0], [1.0, 0.0], [0.0, 1.0]]

    clusters = cluster_questions(questions, embeddings)

    assert len(clusters) == 1
    assert sorted(clusters[0].questions) == ["튜플 만드는 법", "튜플 어떻게 만들어"]
    assert clusters[0].size == MIN_CLUSTER_SIZE


def test_clusters_are_ordered_by_frequency_desc():
    """크기(빈도) 내림차순으로 정렬된다."""
    questions = ["a1", "a2", "a3", "b1", "b2"]
    embeddings = [[1.0, 0.0]] * 3 + [[0.0, 1.0]] * 2

    clusters = cluster_questions(questions, embeddings)

    assert [c.size for c in clusters] == [3, 2]
    assert sorted(clusters[0].questions) == ["a1", "a2", "a3"]


def test_transitive_similarity_merges_into_one_cluster():
    """A~B, B~C 지만 A와 C는 직접 임계값 미만이어도 union-find 로 한 덩어리가 된다."""
    # 0°, 30°, 60° 단위벡터: 인접(30°)은 cos≈0.866≥0.80, 양끝(60°)은 cos=0.5<0.80
    questions = ["q0", "q30", "q60"]
    embeddings = [
        [1.0, 0.0],
        [0.8660254, 0.5],
        [0.5, 0.8660254],
    ]

    clusters = cluster_questions(questions, embeddings)

    assert len(clusters) == 1
    assert clusters[0].size == 3


def test_all_singletons_return_empty():
    """서로 안 비슷하면(모두 크기1) 살아남는 클러스터가 없다."""
    questions = ["x", "y"]
    embeddings = [[1.0, 0.0], [0.0, 1.0]]

    assert cluster_questions(questions, embeddings) == []


def test_empty_input_returns_empty():
    assert cluster_questions([], []) == []


def test_threshold_boundary_links_at_or_above():
    """유사도가 임계값과 정확히 같으면 연결된다(>= 규칙)."""
    # cos = SIMILARITY_THRESHOLD 가 되도록 각도를 맞춘 단위벡터
    import math

    angle = math.acos(SIMILARITY_THRESHOLD)
    questions = ["p", "q"]
    embeddings = [[1.0, 0.0], [math.cos(angle), math.sin(angle)]]

    clusters = cluster_questions(questions, embeddings)

    assert len(clusters) == 1
    assert clusters[0].size == 2
