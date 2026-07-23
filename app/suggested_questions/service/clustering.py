"""
질문 임베딩 벡터를 '의미가 비슷한 것끼리' 묶는다 (순수 파이썬 손구현).
recommendation/apriori.py 처럼 라이브러리 없이 직접 구현한다.

방식: 연결요소(union-find)
  - 두 질문의 코사인 유사도 >= SIMILARITY_THRESHOLD 면 '간선'으로 연결
  - 연결된 덩어리 = 하나의 클러스터(= 같은 유형 질문 묶음)
  - 클러스터 크기 = 그 유형을 물은 횟수 = '빈도'
  - 크기 < MIN_CLUSTER_SIZE 인 클러스터는 노이즈로 버린다
"""
import math
from dataclasses import dataclass

# --- 튜닝 상수 (apriori.py의 MIN_SUPPORT_COUNT 처럼 한 곳에 모아둔다) ---
SIMILARITY_THRESHOLD = 0.80   # 코사인 유사도 임계값. 품질의 핵심 손잡이.
MIN_CLUSTER_SIZE = 2          # 크기 1(한 번만 물은 것)은 '자주'가 아니므로 버림


@dataclass
class QuestionCluster:
    """한 유형(클러스터). questions는 원본 질문들, size는 빈도."""
    questions: list[str]

    @property
    def size(self) -> int:
        return len(self.questions)


def _l2_normalize(vector: list[float]) -> list[float]:
    """벡터를 길이 1로 정규화 → 코사인 유사도를 '내적'만으로 계산 가능."""
    norm = math.sqrt(sum(x * x for x in vector))
    if norm == 0.0:
        return vector
    return [x / norm for x in vector]


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """정규화된 두 벡터의 코사인 유사도 = 내적."""
    return sum(x * y for x, y in zip(a, b))


class _UnionFind:
    """연결요소를 구하는 자료구조 (합치기 union / 찾기 find)."""

    def __init__(self, n: int):
        self._parent = list(range(n))   # 처음엔 각자 자기 자신이 루트

    def find(self, x: int) -> int:
        while self._parent[x] != x:
            self._parent[x] = self._parent[self._parent[x]]   # 경로 압축
            x = self._parent[x]
        return x

    def union(self, a: int, b: int) -> None:
        root_a, root_b = self.find(a), self.find(b)
        if root_a != root_b:
            self._parent[root_b] = root_a


def cluster_questions(
    questions: list[str],
    embeddings: list[list[float]],
) -> list[QuestionCluster]:
    """질문 + 임베딩 벡터 → 크기 내림차순 클러스터 목록(크기<MIN 제외).

    전제: questions[i] 의 임베딩이 embeddings[i] (같은 순서·같은 길이).
    """
    normalized = [_l2_normalize(v) for v in embeddings]
    n = len(questions)
    uf = _UnionFind(n)

    # 모든 쌍(i<j) 비교 → 임계값 넘으면 연결. n<=150 이라 n^2 도 무비용.
    for i in range(n):
        for j in range(i + 1, n):
            if _cosine_similarity(normalized[i], normalized[j]) >= SIMILARITY_THRESHOLD:
                uf.union(i, j)

    # 같은 루트끼리 질문을 모은다
    groups: dict[int, list[str]] = {}
    for idx in range(n):
        root = uf.find(idx)
        groups.setdefault(root, []).append(questions[idx])

    # 크기 필터 + 빈도(크기) 내림차순
    clusters = [QuestionCluster(questions=qs) for qs in groups.values()]
    clusters = [c for c in clusters if c.size >= MIN_CLUSTER_SIZE]
    clusters.sort(key=lambda c: c.size, reverse=True)
    return clusters
