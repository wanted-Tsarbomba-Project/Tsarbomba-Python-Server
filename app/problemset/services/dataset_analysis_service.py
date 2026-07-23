import codecs
import csv
import io
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

from app.problemset.core.config import get_settings


SUPPORTED_ENCODINGS = ("utf-8-sig", "utf-8", "cp949", "ms949", "euc-kr")


def analyze_csv_dataset(dataset_url: str, data_file_name: str | None = None) -> dict[str, Any]:
    """
    Signed URL 또는 허용된 로컬 경로의 CSV 데이터셋 일부만 읽어 문제 생성에 필요한 메타데이터를 반환한다.

    Gemini가 실제 컬럼명, 샘플 행, 인코딩 정보를 바탕으로 문제와 테스트케이스 초안을 만들 수 있게 한다.
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
    max_bytes = settings.dataset_sample_max_bytes
    headers = {"Range": f"bytes=0-{max_bytes}"}

    try:
        content = bytearray()
        with httpx.stream("GET", dataset_url, headers=headers, timeout=10.0) as response:
            response.raise_for_status()

            for chunk in response.iter_bytes():
                remaining = max_bytes + 1 - len(content)
                if remaining <= 0:
                    break
                content.extend(chunk[:remaining])

        sample_bytes, truncated = _limit_sample_bytes(bytes(content), max_bytes)
        return _decode_csv_bytes(sample_bytes, {"dataset_url": dataset_url}, truncated)
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
        raw_content = file.read(settings.dataset_sample_max_bytes + 1)

    sample_bytes, truncated = _limit_sample_bytes(raw_content, settings.dataset_sample_max_bytes)
    return _decode_csv_bytes(sample_bytes, {"dataset_path": str(resolved_path)}, truncated)


def _limit_sample_bytes(content: bytes, max_bytes: int) -> tuple[bytes, bool]:
    truncated = len(content) > max_bytes
    return content[:max_bytes], truncated


def _decode_csv_bytes(content: bytes, meta: dict[str, Any], truncated: bool) -> dict[str, Any]:
    if not content:
        return {"error": "데이터셋 내용이 비어 있습니다.", **meta}

    for encoding in SUPPORTED_ENCODINGS:
        try:
            text = _decode_sample_bytes(content, encoding, truncated)
            return _parse_csv_text(text, encoding, meta, truncated)
        except UnicodeDecodeError:
            continue

    return {"error": "CSV 인코딩을 해석할 수 없습니다.", **meta, "truncated": truncated}


def _decode_sample_bytes(content: bytes, encoding: str, truncated: bool) -> str:
    decoder = codecs.getincrementaldecoder(encoding)(errors="strict")

    # 잘린 샘플은 끝의 불완전한 멀티바이트 문자만 버퍼에 남기고 정상 부분을 반환한다.
    # 잘리지 않은 샘플은 final=True로 엄격하게 검증해 실제 인코딩 오류를 숨기지 않는다.
    return decoder.decode(content, final=not truncated)


def _parse_csv_text(
    text: str,
    encoding: str,
    meta: dict[str, Any],
    truncated: bool,
) -> dict[str, Any]:
    rows = list(csv.reader(io.StringIO(text)))
    if not rows:
        return {"error": "CSV 행을 읽을 수 없습니다.", "encoding": encoding, **meta, "truncated": truncated}

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
        "truncated": truncated,
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