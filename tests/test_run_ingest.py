from types import SimpleNamespace

import pytest

from ingestion import run_ingest


def test_empty_mysql_result_preserves_existing_chroma_index(monkeypatch):
    monkeypatch.setattr(
        run_ingest,
        "get_settings",
        lambda: SimpleNamespace(learning_embedding_batch_size=50),
    )
    monkeypatch.setattr(run_ingest, "fetch_active_problem_sets", lambda: [])

    class UnexpectedVectorStore:
        def __init__(self):
            raise AssertionError("Chroma must not be opened for an empty DB result")

    monkeypatch.setattr(
        run_ingest,
        "LearningProblemSetVectorStore",
        UnexpectedVectorStore,
    )

    with pytest.raises(
        RuntimeError,
        match="No ACTIVE problem sets found; existing Chroma index was preserved",
    ):
        run_ingest.run_ingestion()
