from types import SimpleNamespace

import pytest

from app.problemset.services import dataset_analysis_service


def test_mixed_case_remote_scheme_is_treated_as_url(monkeypatch):
    def fake_read_csv_url(dataset_url: str):
        return {
            "dataset_url": dataset_url,
            "columns": ["id"],
            "sample_rows": [["1"]],
        }

    monkeypatch.setattr(dataset_analysis_service, "_read_csv_url", fake_read_csv_url)
    monkeypatch.setattr(
        dataset_analysis_service,
        "_read_csv_path",
        lambda _path: pytest.fail("mixed-case URL scheme should not be treated as a local path"),
    )

    result = dataset_analysis_service.analyze_csv_dataset(
        "HTTPS://storage.googleapis.com/bucket/data.csv",
    )

    assert result["dataset_url"] == "HTTPS://storage.googleapis.com/bucket/data.csv"
    assert result["data_file_name"] == "data.csv"


def test_csv_url_reader_rejects_redirect_response(monkeypatch):
    class RedirectResponse:
        status_code = 302

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def iter_bytes(self):
            pytest.fail("redirect response body should not be parsed as CSV")

    def fake_stream(_method, _url, headers, timeout):
        assert headers == {"Range": "bytes=0-1024"}
        assert timeout == 10.0
        return RedirectResponse()

    monkeypatch.setattr(dataset_analysis_service, "_validate_dataset_url", lambda _url: None)
    monkeypatch.setattr(
        dataset_analysis_service,
        "get_settings",
        lambda: SimpleNamespace(dataset_sample_max_bytes=1024),
    )
    monkeypatch.setattr(dataset_analysis_service.httpx, "stream", fake_stream)

    result = dataset_analysis_service._read_csv_url(
        "https://storage.googleapis.com/bucket/data.csv",
    )

    assert result["status_code"] == 302
    assert "error" in result
