from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from bot.db import Session, get_or_create_user
from bot.keyboards import choice, main_menu

router = Router()

BUSINESS_TYPES = ["Товары", "Услуги", "Инфопродукты", "Эксперт / блогер", "Другое"]
TONES = ["Дружелюбный", "Экспертный", "Дерзкий"]


class Onboarding(StatesGroup):
    business_type = State()
    business = State()
    audience = State()
    channels = State()
    tone = State()


async def start_onboarding(message: Message, state: FSMContext) -> None:
    await state.set_state(Onboarding.business_type)
    await message.answer(
        "Я ваш AI-маркетолог. Сначала 5 коротких вопросов, чтобы советы были про ваш бизнес.\n\n"
        "1/5. Чем вы занимаетесь?",
        reply_markup=choice(BUSINESS_TYPES, "bt"),
    )


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    async with Session() as session:
        user = await get_or_create_user(session, message.from_user.id, message.from_user.username)
    if user.onboarded:
        await message.answer("С возвращением! Что делаем?", reply_markup=main_menu())
    else:
        await start_onboarding(message, state)


@router.message(Command("profile"))
async def cmd_profile(message: Message, state: FSMContext) -> None:
    await start_onboarding(message, state)


@router.callback_query(Onboarding.business_type, F.data.startswith("bt:"))
async def set_business_type(call: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(business_type=BUSINESS_TYPES[int(call.data.split(":")[1])])
    await state.set_state(Onboarding.business)
    await call.message.answer("2/5. Опишите бизнес одной фразой.")
    await call.answer()


@router.message(Onboarding.business, F.text)
async def set_business(message: Message, state: FSMContext) -> None:
    await state.update_data(business=message.text)
    await state.set_state(Onboarding.audience)
    await message.answer("3/5. Кто ваш клиент? Возраст, город, какая у него проблема.")


@router.message(Onboarding.audience, F.text)
async def set_audience(message: Message, state: FSMContext) -> None:
    await state.update_data(audience=message.text)
    await state.set_state(Onboarding.channels)
    await message.answer("4/5. Где продвигаетесь? Например: Telegram, VK, Авито, сайт, маркетплейсы.")


@router.message(Onboarding.channels, F.text)
async def set_channels(message: Message, state: FSMContext) -> None:
    await state.update_data(channels=message.text)
    await state.set_state(Onboarding.tone)
    await message.answer("5/5. Какой тон у вашего бренда?", reply_markup=choice(TONES, "tone"))


@router.callback_query(Onboarding.tone, F.data.startswith("tone:"))
async def set_tone(call: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    async with Session() as session:
        user = await get_or_create_user(session, call.from_user.id, call.from_user.username)
        user.business_type = data["business_type"]
        user.business = data["business"]
        user.audience = data["audience"]
        user.channels = data["channels"]
        user.tone = TONES[int(call.data.split(":")[1])]
        await session.commit()
    await state.clear()
    await call.message.answer(
        f"Готово, профиль сохранён. Бесплатных запросов: {user.requests_left}.\n\nЧто делаем?",
        reply_markup=main_menu(),
    )
    await call.answer()
