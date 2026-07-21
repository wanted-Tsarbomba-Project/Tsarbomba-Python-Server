import csv
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

from core.config import get_settings


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
    validation_error = _validate_dataset_url(dataset_url)
    if validation_error:
        return validation_error

    settings = get_settings()
    headers = {"Range": f"bytes=0-{settings.dataset_sample_max_bytes - 1}"}

    try:
        content = bytearray()
        with httpx.stream("GET", dataset_url, headers=headers, timeout=10.0) as response:
            response.raise_for_status()

            for chunk in response.iter_bytes():
                remaining = settings.dataset_sample_max_bytes - len(content)
                if remaining <= 0:
                    break

                content.extend(chunk[:remaining])

        return _decode_csv_bytes(bytes(content), {"dataset_url": dataset_url})
    except httpx.TimeoutException:
        return {"error": "데이터셋 URL 응답이 지연되고 있습니다."}
    except httpx.HTTPStatusError as exc:
        return {
            "error": "데이터셋 URL 접근에 실패했습니다.",
            "status_code": exc.response.status_code,
        }
    except Exception as exc:
        return {
            "error": "데이터셋 URL 요청 중 오류가 발생했습니다.",
            "exception_type": exc.__class__.__name__,
        }


def _read_csv_path(path: Path) -> dict[str, Any]:
    settings = get_settings()

    if not settings.allow_local_dataset_path:
        return {"error": "로컬 데이터셋 경로 접근은 허용되지 않습니다."}

    safe_dir = Path(settings.safe_dataset_dir).expanduser().resolve()
    resolved_path = path.expanduser().resolve()

    if not resolved_path.is_relative_to(safe_dir):
        return {"error": "허용되지 않은 데이터셋 경로입니다."}

    if not resolved_path.exists():
        return {"error": "데이터셋 파일을 찾을 수 없습니다.", "dataset_path": str(resolved_path)}
    if not resolved_path.is_file():
        return {"error": "데이터셋 경로가 파일이 아닙니다.", "dataset_path": str(resolved_path)}

    with resolved_path.open("rb") as file:
        content = file.read(settings.dataset_sample_max_bytes)

    return _decode_csv_bytes(content, {"dataset_path": str(resolved_path)})


def _validate_dataset_url(dataset_url: str) -> dict[str, Any] | None:
    parsed = urlparse(dataset_url)

    if parsed.scheme != "https":
        return {"error": "데이터셋 URL은 https만 허용됩니다."}

    hostname = parsed.hostname
    if not hostname:
        return {"error": "데이터셋 URL 호스트를 확인할 수 없습니다."}

    allowed_hosts = get_settings().allowed_dataset_url_hosts
    if not _is_allowed_host(hostname, allowed_hosts):
        return {
            "error": "허용되지 않은 데이터셋 URL 호스트입니다.",
            "host": hostname,
        }

    return None


def _is_allowed_host(hostname: str, allowed_hosts: tuple[str, ...]) -> bool:
    for allowed_host in allowed_hosts:
        if allowed_host.startswith("*."):
            suffix = allowed_host[1:]
            if hostname.endswith(suffix):
                return True
        elif hostname == allowed_host:
            return True

    return False


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
