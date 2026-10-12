from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.prompts import SCENARIOS


def main_menu() -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text=title, callback_data=f"sc:{key}")] for key, (title, _, _) in SCENARIOS.items()]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def after_answer() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔄 Переписать", callback_data="act:rewrite"),
            InlineKeyboardButton(text="✂️ Короче", callback_data="act:shorter"),
        ],
        [InlineKeyboardButton(text="🏠 В меню", callback_data="act:menu")],
    ])


def choice(options: list[str], prefix: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=o, callback_data=f"{prefix}:{i}")] for i, o in enumerate(options)]
    )
