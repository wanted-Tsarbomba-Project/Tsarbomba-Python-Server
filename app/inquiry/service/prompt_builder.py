from app.inquiry.schema.inquiry import CorrectionExample, InquiryAnalyzeRequest, InquiryDomain, InquirySeverity

# Java InquiryDomain.SCHEMA_DESCRIPTION / InquirySeverity.SCHEMA_DESCRIPTION과 동일한 설명을 유지한다.
# 설명 없이 enum 값만 주면 Gemini가 BADGE/ENROLLMENT/LECTURE처럼 헷갈리기 쉬운 도메인을
# 근거 없이 추측하게 되므로, 관리자가 Swagger에서 보는 것과 같은 힌트를 그대로 넘긴다.
_DOMAIN_DESCRIPTIONS = {
    InquiryDomain.ADMIN: "관리자/운영",
    InquiryDomain.AUTH: "로그인/인증",
    InquiryDomain.BADGE: "뱃지",
    InquiryDomain.CHATBOT: "챗봇",
    InquiryDomain.COURSE: "강의",
    InquiryDomain.ENROLLMENT: "수강신청/수강관리",
    InquiryDomain.PROBLEMS: "문제/채점/제출",
    InquiryDomain.RANKING: "랭킹",
    InquiryDomain.RECOMMENDATION: "추천",
    InquiryDomain.USER: "회원/프로필",
    InquiryDomain.LECTURE: "강의 영상/자료",
    InquiryDomain.LEARNING: "학습 진행",
    InquiryDomain.ETC: "기타",
}

_SEVERITY_DESCRIPTIONS = {
    InquirySeverity.LOW: "단순 문의/제안",
    InquirySeverity.MEDIUM: "일반 오류/불편",
    InquirySeverity.HIGH: "기능 사용에 큰 지장",
    InquirySeverity.CRITICAL: "로그인/결제/학습 진행 불가급",
}


def build_analysis_prompt(request: InquiryAnalyzeRequest) -> str:
    """문의 원문 + 관리자 보정 사례로 Gemini 분석 프롬프트를 조립한다."""
    domain_values = ", ".join(f"{domain.value}: {_DOMAIN_DESCRIPTIONS[domain]}" for domain in InquiryDomain)
    severity_values = ", ".join(
        f"{severity.value}: {_SEVERITY_DESCRIPTIONS[severity]}" for severity in InquirySeverity
    )
    correction_section = _build_correction_section(request.correction_examples)

    return (
        "너는 LMS 서비스의 사용자 문의를 분류하는 운영 보조 AI다.\n"
        "아래 문의를 분석해서 반드시 지정된 JSON으로만 응답해라. 다른 설명 텍스트는 절대 붙이지 마라.\n\n"
        f"[문의 원문]\n{request.content}\n\n"
        f"[문의가 작성된 페이지 경로]\n{request.source_url or '알 수 없음'}\n\n"
        f"[domain 후보 — 반드시 이 중 하나]\n{domain_values}\n\n"
        f"[severity 기준 — 반드시 이 중 하나]\n{severity_values}\n\n"
        f"{correction_section}"
        "[출력 JSON 스키마]\n"
        "{\n"
        '  "title": "문의 핵심을 요약한 15자 내외 제목",\n'
        '  "summary": "관리자가 빠르게 파악할 수 있는 1~2문장 요약",\n'
        '  "severity": "위 severity 후보 중 하나",\n'
        '  "domain": "위 domain 후보 중 하나",\n'
        '  "estimated_url": "문제가 발생한 것으로 추정되는 경로, 확신 없으면 문의가 작성된 페이지 경로 그대로",\n'
        '  "recommended_action": "관리자가 다음에 취해야 할 조치 1~2문장",\n'
        '  "filtered": true 또는 false (스팸/광고/의미 없는 문의면 true)\n'
        "}\n"
    )


def _build_correction_section(correction_examples: list[CorrectionExample]) -> str:
    if not correction_examples:
        return ""

    # "표현이 비슷하면 같은 결론"이라는 규칙 매칭으로 읽히지 않도록,
    # 사례의 결론(ai_value → corrected_value) 자체가 아니라 관리자가 남긴
    # 판단 기준(reason)을 이해해서 이번 문의에 맞게 스스로 판단하도록 지시한다.
    lines = [
        f"- {example.field_name} 관련: 관리자는 '{example.reason}'라는 기준으로 "
        f"'{example.ai_value}' 대신 '{example.corrected_value}'가 맞다고 판단함"
        for example in correction_examples
    ]
    return (
        "[관리자 보정 사례]\n"
        "아래는 과거 AI 판단과 관리자의 최종 판단이 달랐던 사례다. "
        "문의 표현이 비슷하다고 기계적으로 같은 결론을 내리지 마라. "
        "각 사례에서 관리자가 어떤 기준(이유)으로 판단했는지를 이해하고, "
        "그 기준이 이번 문의에도 실제로 적용되는지 스스로 판단해서 반영해라. "
        "기준이 적용되지 않는 새로운 상황이면 사례를 억지로 끼워 맞추지 말고 독립적으로 판단해라.\n"
        + "\n".join(lines) + "\n\n"
    )
