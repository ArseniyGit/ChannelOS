import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.exceptions import TelegramNetworkError
from aiogram.types import MenuButtonWebApp, WebAppInfo

from bot.handlers import router, sync_all_managed_groups
from core.settings.config import settings


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
RETRY_DELAY_SECONDS = 5


async def sync_menu_button() -> None:
    """Keep profile menu button aligned with current WEBAPP_URL."""
    try:
        await bot.set_chat_menu_button(
            menu_button=MenuButtonWebApp(
                text="Открыть приложение",
                web_app=WebAppInfo(url=settings.WEBAPP_URL),
            )
        )
        logger.info("✅ Menu button synced to WEBAPP_URL: %s", settings.WEBAPP_URL)
    except Exception:
        logger.exception("Failed to sync chat menu button with WEBAPP_URL")


async def start_bot():
    dp = Dispatcher()
    dp.include_router(router)
    logger.info("🤖 Бот запускается...")
    logger.info(f"📱 Bot ID: {settings.TELEGRAM_BOT_TOKEN.split(':')[0]}")
    await sync_menu_button()
    await sync_all_managed_groups(bot)

    while True:
        try:
            await dp.start_polling(bot)
            logger.warning(
                "Polling stopped without exception, retrying in %s seconds",
                RETRY_DELAY_SECONDS,
            )
        except TelegramNetworkError as exc:
            logger.warning(
                "Telegram network error, retrying in %s seconds: %s",
                RETRY_DELAY_SECONDS,
                exc,
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception(
                "Unexpected bot polling crash, retrying in %s seconds",
                RETRY_DELAY_SECONDS,
            )

        await asyncio.sleep(RETRY_DELAY_SECONDS)

if __name__ == "__main__":
    asyncio.run(start_bot())
