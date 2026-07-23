from app.problemset.clients.gemini_client import ProblemSetGeminiClient
from app.problemset.schemas.problem_set_draft_schema import ChatRequest, ChatResponse


class ProblemSetDraftService:
    def __init__(self) -> None:
        self.gemini_client = ProblemSetGeminiClient()

    def generate(self, request: ChatRequest) -> ChatResponse:
        answer, draft, used_tools = self.gemini_client.generate(request)
        return ChatResponse(
            answer=answer,
            draft=draft,
            used_tools=used_tools,
        )
