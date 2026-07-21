"""운영 Q&A 챗봇 시스템 프롬프트 조립.

templates/system_ops.j2 에 현재 KST 시각을 주입한다 — DB created_at 이 KST 벽시계라서
LLM 이 "어제/최근 1시간" 을 KST 기준 명시적 start/end 로 변환하게 하는 핵심 장치.
"""

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from jinja2 import Environment, FileSystemLoader

# templates/ 디렉토리 기준 (app/opschat/service → 프로젝트 루트)
_TEMPLATES_DIR = Path(__file__).parent.parent.parent.parent / "templates"
_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATES_DIR)),
    trim_blocks=True,
    lstrip_blocks=True,
)

KST = timezone(timedelta(hours=9))
_WEEKDAYS_KO = ["월", "화", "수", "목", "금", "토", "일"]


def build_ops_system_prompt(max_length: int, now: Optional[datetime] = None) -> str:
    """system_ops.j2 렌더. now 는 테스트 주입용 — 미지정 시 현재 KST."""
    if now is None:
        now = datetime.now(KST)
    now_kst = f"{now:%Y-%m-%d %H:%M:%S} ({_WEEKDAYS_KO[now.weekday()]}요일)"

    template = _env.get_template("system_ops.j2")
    return template.render(now_kst=now_kst, max_length=max_length)
