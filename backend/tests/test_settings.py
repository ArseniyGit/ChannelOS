from core.settings.config import Settings


def test_settings_accepts_single_numeric_admin_id() -> None:
    settings = Settings(
        DATABASE_URL="sqlite+aiosqlite:///./test_settings.db",
        TELEGRAM_BOT_TOKEN="123456:ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghi",
        WEBAPP_URL="https://example.test",
        ADMIN_IDS=1,
        _env_file=None,
    )

    assert settings.ADMIN_IDS == [1]
