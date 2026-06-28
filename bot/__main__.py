"""Точка входа: python -m bot"""

from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher

from . import deepseek
from .config import settings
from .handlers import setup_routers

log = logging.getLogger("shalunbot")


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    bot = Bot(token=settings.bot_token)  # без parse_mode — шлём чистый текст
    dp = Dispatcher()

    me = await bot.get_me()
    dp["bot_username"] = me.username  # прокидывается в хендлеры как kwarg
    log.info(
        "Запущен как @%s (id=%s), персона «%s», модель %s",
        me.username, me.id, settings.persona_name, settings.deepseek_model,
    )

    dp.include_router(setup_routers())

    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await deepseek.aclose()
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        log.info("Остановлен")
