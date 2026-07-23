import csv
import io
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

from app.problemset.core.config import get_settings


def analyze_csv_dataset(dataset_url: str, data_file_name: str | None = None) -> dict[str, Any]:
    """
    Signed URL 또는 허용된 로컬 경로의 CSV 데이터셋을 일부만 읽어 문제 생성에 필요한 메타데이터를 반환한다.

    Gemini는 이 결과를 바탕으로 실제 컬럼명, 샘플 값, 인코딩을 확인한 뒤 문제와 테스트케이스 초안을 만든다.
    """
    if dataset_url.startswith(("http://", "https://")):
        result = _read_csv_url(dataset_url)
    else:
        result = _read_csv_path(Path(dataset_url))

    if "error" in result:
        return result

    result["data_file_name"] = data_file_name or infer_file_name(dataset_url)
    return result


def infer_file_name(dataset_url: str) -> str:
    parsed = urlparse(dataset_url)
    if parsed.scheme:
        file_name = Path(parsed.path).name
    else:
        file_name = Path(dataset_url).name

    return file_name or "dataset.csv"


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

    safe_dir = Path(settings.safe_dataset_dir).resolve()
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


def _decode_csv_bytes(content: bytes, meta: dict[str, Any]) -> dict[str, Any]:
    if not content:
        return {"error": "데이터셋 내용이 비어 있습니다.", **meta}

    for encoding in ("utf-8-sig", "utf-8", "cp949", "ms949", "euc-kr"):
        try:
            text = content.decode(encoding)
            return _parse_csv_text(text, encoding, meta)
        except UnicodeDecodeError:
            continue

    return {"error": "CSV 인코딩을 해석할 수 없습니다.", **meta}


def _parse_csv_text(text: str, encoding: str, meta: dict[str, Any]) -> dict[str, Any]:
    rows = list(csv.reader(io.StringIO(text)))
    if not rows:
        return {"error": "CSV 행을 읽을 수 없습니다.", "encoding": encoding, **meta}

    columns = rows[0]
    unique_columns = _make_unique_columns(columns)
    sample_rows = rows[1:21]
    sample_records = [_to_record(unique_columns, row) for row in sample_rows]

    return {
        **meta,
        "encoding": encoding,
        "column_count": len(columns),
        "columns": columns,
        "normalized_columns": unique_columns,
        "sample_row_count": len(sample_rows),
        "sample_rows": sample_rows,
        "sample_records": sample_records,
        "truncated": len(text.encode(encoding, errors="ignore")) >= get_settings().dataset_sample_max_bytes,
    }


def _make_unique_columns(columns: list[str]) -> list[str]:
    seen: dict[str, int] = {}
    result: list[str] = []

    for index, column in enumerate(columns):
        base = column.strip() or f"column_{index + 1}"
        count = seen.get(base, 0)
        seen[base] = count + 1
        result.append(base if count == 0 else f"{base}.{count}")

    return result


def _to_record(columns: list[str], row: list[str]) -> dict[str, str]:
    return {
        column: row[index] if index < len(row) else ""
        for index, column in enumerate(columns)
    }


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
