import logging

from aiogram import F, Router
from aiogram.enums import ChatAction
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from bot import llm
from bot.db import Session, get_or_create_user
from bot.keyboards import after_answer, main_menu
from bot.prompts import BASE_PROMPT, SCENARIOS

router = Router()
log = logging.getLogger(__name__)

TELEGRAM_LIMIT = 4096
HISTORY_LIMIT = 10  # сообщений диалога, которые помним внутри сценария


class Chat(StatesGroup):
    active = State()


@router.callback_query(F.data.startswith("sc:"))
async def open_scenario(call: CallbackQuery, state: FSMContext) -> None:
    key = call.data.split(":")[1]
    title, question, _ = SCENARIOS[key]
    await state.set_state(Chat.active)
    await state.update_data(scenario=key, history=[])
    await call.message.answer(f"{title}\n\n{question}")
    await call.answer()


@router.callback_query(F.data == "act:menu")
async def back_to_menu(call: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await call.message.answer("Что делаем?", reply_markup=main_menu())
    await call.answer()


@router.callback_query(Chat.active, F.data.in_({"act:rewrite", "act:shorter"}))
async def refine(call: CallbackQuery, state: FSMContext) -> None:
    text = "Перепиши иначе, другими словами." if call.data == "act:rewrite" else "Сделай заметно короче."
    await call.answer()
    await run_llm(call.message, call.from_user.id, call.from_user.username, state, text)


@router.message(Chat.active, F.text)
async def scenario_message(message: Message, state: FSMContext) -> None:
    await run_llm(message, message.from_user.id, message.from_user.username, state, message.text)


@router.message(F.text)
async def no_scenario(message: Message) -> None:
    await message.answer("Выберите, с чем помочь:", reply_markup=main_menu())


async def run_llm(message: Message, user_id: int, username: str | None, state: FSMContext, text: str) -> None:
    async with Session() as session:
        user = await get_or_create_user(session, user_id, username)
        if user.requests_left <= 0:
            # TODO: оплата (Telegram Stars + ЮKassa), неделя 4
            await message.answer("Бесплатные запросы закончились. Скоро здесь появятся тарифы.")
            return

        data = await state.get_data()
        _, _, instruction = SCENARIOS[data["scenario"]]
        system = BASE_PROMPT.format(profile=user.profile_text()) + f"\n\nЗадача: {instruction}"
        history = data.get("history", []) + [{"role": "user", "content": text}]

        await message.bot.send_chat_action(message.chat.id, ChatAction.TYPING)
        try:
            answer = await llm.ask(system, history)
        except Exception:
            log.exception("LLM request failed")
            await message.answer("Не получилось получить ответ, попробуйте ещё раз через минуту.")
            return

        user.requests_left -= 1
        await session.commit()

    history.append({"role": "assistant", "content": answer})
    await state.update_data(history=history[-HISTORY_LIMIT:])
    for i in range(0, len(answer), TELEGRAM_LIMIT):
        chunk = answer[i:i + TELEGRAM_LIMIT]
        is_last = i + TELEGRAM_LIMIT >= len(answer)
        await message.answer(chunk, reply_markup=after_answer() if is_last else None)
