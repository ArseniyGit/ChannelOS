from core.settings.config import settings
from core.utils.webapp_urls import append_query_params, build_webapp_return_url


def test_append_query_params_preserves_existing_and_adds_new() -> None:
    url = append_query_params("https://example.test/payment-success?foo=1", bot="coreftestbot")
    assert "foo=1" in url
    assert "bot=coreftestbot" in url


def test_build_webapp_return_url_adds_bot_username_when_present(monkeypatch) -> None:
    monkeypatch.setattr(settings, "WEBAPP_URL", "https://example.test")
    monkeypatch.setattr(settings, "TELEGRAM_BOT_USERNAME", "coreftestbot")
    monkeypatch.setattr(settings, "TELEGRAM_MINI_APP_SHORT_NAME", "")

    url = build_webapp_return_url("/payment-success")
    assert url == "https://example.test/payment-success?bot=coreftestbot"


def test_build_webapp_return_url_adds_bot_and_app_short_name(monkeypatch) -> None:
    monkeypatch.setattr(settings, "WEBAPP_URL", "https://example.test")
    monkeypatch.setattr(settings, "TELEGRAM_BOT_USERNAME", "coreftestbot")
    monkeypatch.setattr(settings, "TELEGRAM_MINI_APP_SHORT_NAME", "miniapp")

    url = build_webapp_return_url("/payment-success")
    assert url == "https://example.test/payment-success?bot=coreftestbot&app=miniapp"


def test_build_webapp_return_url_without_bot_username(monkeypatch) -> None:
    monkeypatch.setattr(settings, "WEBAPP_URL", "https://example.test")
    monkeypatch.setattr(settings, "TELEGRAM_BOT_USERNAME", "")
    monkeypatch.setattr(settings, "TELEGRAM_MINI_APP_SHORT_NAME", "")

    url = build_webapp_return_url("payment-cancel")
    assert url == "https://example.test/payment-cancel"
