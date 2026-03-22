from pathlib import Path

from core.services import media_urls


def test_to_upload_relative_path_from_absolute_url() -> None:
    value = "https://old.trycloudflare.com/uploads/a1b2c3.jpg"
    assert media_urls.to_upload_relative_path(value) == "/uploads/a1b2c3.jpg"


def test_to_upload_relative_path_rejects_nested_path() -> None:
    value = "https://old.trycloudflare.com/uploads/nested/file.jpg"
    assert media_urls.to_upload_relative_path(value) is None


def test_normalize_media_urls_converts_uploads_and_keeps_external() -> None:
    raw = "https://old.trycloudflare.com/uploads/a.jpg, https://example.com/pic.png, /uploads/a.jpg"
    assert media_urls.normalize_media_urls(raw) == "/uploads/a.jpg,https://example.com/pic.png"


def test_split_media_urls_handles_empty() -> None:
    assert media_urls.split_media_urls(None) == []
    assert media_urls.split_media_urls(" , , ") == []


def test_resolve_upload_local_file_finds_existing(tmp_path: Path, monkeypatch) -> None:
    fake_uploads = tmp_path / "uploads"
    fake_uploads.mkdir(parents=True, exist_ok=True)
    fake_file = fake_uploads / "x1.jpg"
    fake_file.write_bytes(b"test")

    monkeypatch.setattr(media_urls, "_uploads_dir", lambda: fake_uploads)

    resolved = media_urls.resolve_upload_local_file("/uploads/x1.jpg")
    assert resolved is not None
    assert resolved.name == "x1.jpg"

