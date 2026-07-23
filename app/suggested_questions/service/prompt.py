"""
라벨링(대표 질문 생성) 프롬프트 조립.
ADR-0004: 프롬프트 텍스트는 코드에 하드코딩하지 않고 templates/*.j2 에만 둔다.
chatbot/prompt_builder.py 와 같은 방식으로 Jinja2 로 렌더한다.
"""
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from app.suggested_questions.service.clustering import QuestionCluster

# app/suggested_questions/service/prompt.py → 프로젝트 루트/templates
_TEMPLATES_DIR = Path(__file__).resolve().parents[3] / "templates"
_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATES_DIR)),
    trim_blocks=True,
    lstrip_blocks=True,
)


def build_label_prompt(
    clusters: list[QuestionCluster],
    top_n: int,
    sample_per_cluster: int,
) -> str:
    """빈도 상위 후보 클러스터 → 라벨링 프롬프트 문자열."""
    template = _env.get_template("suggested_questions.j2")
    cluster_views = [
        {"size": cluster.size, "samples": cluster.questions[:sample_per_cluster]}
        for cluster in clusters
    ]
    return template.render(clusters=cluster_views, top_n=top_n)
