import hashlib
import hmac
import json
import logging
import time
from urllib.parse import parse_qsl

from core.settings.config import settings

logger = logging.getLogger(__name__)


def validate_telegram_data(init_data: str) -> dict | None:
    """Строгая валидация Telegram WebApp init data."""
    if not init_data:
        logger.warning("validate_telegram_data: empty init_data")
        return None

    try:
        parsed = dict(parse_qsl(init_data, strict_parsing=True))
    except Exception:
        logger.exception("validate_telegram_data: cannot parse init_data")
        return None

    try:
        received_hash = parsed.pop('hash', None)
        if not received_hash:
            logger.warning('validate_telegram_data: no hash in init_data')
            return None

        auth_date_raw = parsed.get("auth_date")
        if not auth_date_raw:
            logger.warning("validate_telegram_data: no auth_date in init_data")
            return None
        try:
            auth_date = int(auth_date_raw)
        except (TypeError, ValueError):
            logger.warning("validate_telegram_data: invalid auth_date=%s", auth_date_raw)
            return None

        now_ts = int(time.time())
        if auth_date > now_ts + 60:
            logger.warning("validate_telegram_data: auth_date from future")
            return None
        if now_ts - auth_date > settings.TELEGRAM_AUTH_MAX_AGE_SECONDS:
            logger.warning("validate_telegram_data: auth_date expired")
            return None

        data_string = '\n'.join(f'{k}={v}' for k, v in sorted(parsed.items()))

        secret = hmac.new(
            b"WebAppData",
            settings.TELEGRAM_BOT_TOKEN.encode(),
            hashlib.sha256
        ).digest()

        calculated = hmac.new(secret, data_string.encode(), hashlib.sha256).hexdigest()

        if not hmac.compare_digest(calculated, received_hash):
            logger.warning("validate_telegram_data: signature mismatch")
            return None

        raw_user = parsed.get("user")
        if not raw_user:
            logger.warning("validate_telegram_data: no user payload")
            return None
        user = json.loads(raw_user)
        telegram_id = user.get("id")
        if not telegram_id:
            logger.warning("validate_telegram_data: user payload without id")
            return None

        result = {
            'telegram_id': telegram_id,
            'username': user.get('username'),
            'first_name': user.get('first_name')
        }
        return result
    except Exception:
        logger.exception('Exception while validating telegram data')
        return None
