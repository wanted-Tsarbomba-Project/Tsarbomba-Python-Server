from fastapi import FastAPI

from app.problemset.routers.problem_set_draft_router import router as problem_set_draft_router

app = FastAPI(title="Code-Bomba Problem Set Generation RAG")
app.include_router(problem_set_draft_router)
