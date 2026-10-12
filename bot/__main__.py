import asyncio
import logging

from aiogram import Bot, Dispatcher

from bot.config import settings
from bot.db import init_db
from bot.handlers import admin, onboarding, scenarios


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    await init_db()
    bot = Bot(settings.bot_token)
    dp = Dispatcher()
    # порядок важен: scenarios содержит общий обработчик текста, он должен быть последним
    dp.include_routers(admin.router, onboarding.router, scenarios.router)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
