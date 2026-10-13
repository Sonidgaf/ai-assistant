from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.prompts import SCENARIOS


def main_menu() -> InlineKeyboardMarkup:
    buttons = [InlineKeyboardButton(text=s.title, callback_data=f"sc:{key}") for key, s in SCENARIOS.items()]
    rows = [buttons[i:i + 2] for i in range(0, len(buttons), 2)]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def examples(scenario_key: str) -> InlineKeyboardMarkup | None:
    items = SCENARIOS[scenario_key].examples
    if not items:
        return None
    rows = [[InlineKeyboardButton(text=f"✨ {text}", callback_data=f"ex:{i}")] for i, text in enumerate(items)]
    rows.append([InlineKeyboardButton(text="🏠 В меню", callback_data="act:menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def after_answer(can_expand: bool = True) -> InlineKeyboardMarkup:
    first_row = [InlineKeyboardButton(text="🔄 Другой вариант", callback_data="act:rewrite")]
    if can_expand:
        first_row.insert(0, InlineKeyboardButton(text="📖 Подробнее", callback_data="act:more"))
    return InlineKeyboardMarkup(inline_keyboard=[
        first_row,
        [InlineKeyboardButton(text="🏠 В меню", callback_data="act:menu")],
    ])


def choice(options: list[str], prefix: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=o, callback_data=f"{prefix}:{i}")] for i, o in enumerate(options)]
    )
