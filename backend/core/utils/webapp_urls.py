from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from core.settings.config import settings


def append_query_params(url: str, **params: str) -> str:
    """Return URL with extra query params while preserving existing ones."""
    split = urlsplit(url)
    query = dict(parse_qsl(split.query, keep_blank_values=True))
    for key, value in params.items():
        if value is None:
            continue
        normalized = str(value).strip()
        if not normalized:
            continue
        query[key] = normalized

    return urlunsplit(
        (
            split.scheme,
            split.netloc,
            split.path,
            urlencode(query),
            split.fragment,
        )
    )


def build_webapp_return_url(path: str) -> str:
    normalized_path = path if path.startswith("/") else f"/{path}"
    url = f"{settings.WEBAPP_URL}{normalized_path}"
    bot_username = settings.TELEGRAM_BOT_USERNAME
    mini_app_short_name = settings.TELEGRAM_MINI_APP_SHORT_NAME
    if bot_username:
        url = append_query_params(url, bot=bot_username)
    if mini_app_short_name:
        url = append_query_params(url, app=mini_app_short_name)
    return url
