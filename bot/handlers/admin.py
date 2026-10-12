from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from bot.config import settings
from bot.db import Session, count_users

router = Router()


@router.message(Command("stats"))
async def cmd_stats(message: Message) -> None:
    if message.from_user.id not in settings.admins:
        return
    async with Session() as session:
        users = await count_users(session)
    await message.answer(f"Пользователей: {users}")
