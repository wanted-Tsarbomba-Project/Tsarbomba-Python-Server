import csv
from pathlib import Path
from typing import Any

import httpx


def analyze_csv_dataset(dataset_url: str, data_file_name: str | None = None) -> dict[str, Any]:
    loaded = _load_csv_text(dataset_url)
    if "error" in loaded:
        return loaded

    rows = _parse_csv_rows(loaded["text"])
    if isinstance(rows, dict) and "error" in rows:
        return rows

    if not rows:
        return {"error": "CSV 파일이 비어 있습니다."}

    header = [column.strip() for column in rows[0]]
    data_rows = rows[1:]
    sample_limit = min(len(data_rows), 20)

    columns: list[dict[str, Any]] = []
    for index, name in enumerate(header):
        samples: list[str] = []
        numeric_count = 0

        for row in data_rows[:sample_limit]:
            if index >= len(row):
                continue

            value = row[index].strip()
            if not value:
                continue

            if value not in samples and len(samples) < 5:
                samples.append(value[:100])

            if _looks_numeric(value):
                numeric_count += 1

        columns.append(
            {
                "name": name,
                "sample_values": samples,
                "numeric_candidate": sample_limit > 0
                and numeric_count >= max(1, sample_limit // 2),
            }
        )

    return {
        "file_name": data_file_name or infer_file_name(dataset_url),
        "encoding": loaded["encoding"],
        "row_count": len(data_rows),
        "column_count": len(header),
        "columns": columns,
    }


def infer_file_name(dataset_url: str) -> str:
    if dataset_url.startswith("http://") or dataset_url.startswith("https://"):
        return "dataset.csv"

    return Path(dataset_url).name


def _load_csv_text(dataset_url: str) -> dict[str, Any]:
    if dataset_url.startswith("http://") or dataset_url.startswith("https://"):
        return _read_csv_url(dataset_url)

    return _read_csv_path(Path(dataset_url))


def _read_csv_url(dataset_url: str) -> dict[str, Any]:
    try:
        response = httpx.get(dataset_url, timeout=10.0)
        response.raise_for_status()
    except httpx.TimeoutException:
        return {"error": "데이터셋 URL 응답이 지연되고 있습니다."}
    except httpx.HTTPStatusError as exc:
        return {
            "error": "데이터셋 URL 접근에 실패했습니다.",
            "status_code": exc.response.status_code,
            "body": exc.response.text[:300],
        }
    except Exception as exc:
        return {
            "error": "데이터셋 URL 요청 중 오류가 발생했습니다.",
            "exception_type": exc.__class__.__name__,
        }

    return _decode_csv_bytes(response.content, {"dataset_url": dataset_url})


def _read_csv_path(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"error": "데이터셋 파일을 찾을 수 없습니다.", "dataset_path": str(path)}
    if not path.is_file():
        return {"error": "데이터셋 경로가 파일이 아닙니다.", "dataset_path": str(path)}

    return _decode_csv_bytes(path.read_bytes(), {"dataset_path": str(path)})


def _decode_csv_bytes(content: bytes, context: dict[str, str]) -> dict[str, Any]:
    for encoding in ("utf-8-sig", "utf-8", "cp949", "ms949"):
        try:
            return {"text": content.decode(encoding), "encoding": encoding}
        except UnicodeDecodeError:
            continue

    return {
        "error": "CSV 파일 인코딩을 해석할 수 없습니다.",
        **context,
    }


def _parse_csv_rows(text: str) -> list[list[str]] | dict[str, str]:
    try:
        return list(csv.reader(text.splitlines()))
    except csv.Error as exc:
        return {"error": "CSV 파싱에 실패했습니다.", "detail": str(exc)}


def _looks_numeric(value: str) -> bool:
    normalized = value.replace(",", "").replace("%", "").strip()
    try:
        float(normalized)
        return True
    except ValueError:
        return False
