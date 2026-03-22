from pathlib import Path
from urllib.parse import unquote, urlsplit


UPLOADS_PREFIX = "/uploads/"


def split_media_urls(media_url: str | None) -> list[str]:
    if not media_url:
        return []
    return [item.strip() for item in media_url.split(",") if item and item.strip()]


def to_upload_relative_path(value: str) -> str | None:
    raw = (value or "").strip()
    if not raw:
        return None

    path = raw
    if "://" in raw:
        parsed = urlsplit(raw)
        path = unquote(parsed.path or "")

    if not path.startswith(UPLOADS_PREFIX):
        return None

    filename = path[len(UPLOADS_PREFIX):]
    if not filename:
        return None

    # Prevent path traversal and nested directories for uploaded media ids.
    if "/" in filename or "\\" in filename or ".." in filename:
        return None

    return f"{UPLOADS_PREFIX}{filename}"


def normalize_media_urls(media_url: str | None) -> str | None:
    items = split_media_urls(media_url)
    if not items:
        return None

    normalized: list[str] = []
    seen: set[str] = set()
    for item in items:
        current = to_upload_relative_path(item) or item
        if current in seen:
            continue
        seen.add(current)
        normalized.append(current)

    return ",".join(normalized) if normalized else None


def resolve_upload_local_file(value: str) -> Path | None:
    rel = to_upload_relative_path(value)
    if not rel:
        return None

    filename = rel[len(UPLOADS_PREFIX):]
    uploads_dir = _uploads_dir()
    file_path = uploads_dir / filename
    if not file_path.exists() or not file_path.is_file():
        return None
    return file_path


def _uploads_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "uploads"
