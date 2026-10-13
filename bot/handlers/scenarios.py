import logging
from datetime import date

from aiogram import F, Router
from aiogram.enums import ChatAction
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, LinkPreviewOptions, Message

from bot import competitors, llm
from bot.db import Session, get_or_create_user
from bot.formatting import sanitize, split, strip_tags
from bot.keyboards import after_answer, examples, main_menu
from bot.prompts import BASE_PROMPT, LONG_MODE, SCENARIOS, SHORT_MODE

router = Router()
log = logging.getLogger(__name__)

HISTORY_LIMIT = 10  # сообщений диалога, которые помним внутри сценария
NO_PREVIEW = LinkPreviewOptions(is_disabled=True)  # ссылки на источники не раздувают ответ превью


class Chat(StatesGroup):
    active = State()


@router.callback_query(F.data.startswith("sc:"))
async def open_scenario(call: CallbackQuery, state: FSMContext) -> None:
    key = call.data.split(":")[1]
    await state.set_state(Chat.active)
    await state.update_data(scenario=key, history=[])
    await call.message.answer(SCENARIOS[key].intro, reply_markup=examples(key))
    await call.answer()


@router.callback_query(F.data == "act:menu")
async def back_to_menu(call: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await call.message.answer("🏠 <b>Главное меню</b>\n\nЧто делаем?", reply_markup=main_menu())
    await call.answer()


@router.callback_query(Chat.active, F.data.startswith("ex:"))
async def pick_example(call: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    text = SCENARIOS[data["scenario"]].examples[int(call.data.split(":")[1])]
    await call.answer()
    await call.message.answer(f"✨ <i>{sanitize(text)}</i>")
    await run_llm(call.message, call.from_user.id, call.from_user.username, state, text, long=False)


@router.callback_query(Chat.active, F.data == "act:more")
async def more(call: CallbackQuery, state: FSMContext) -> None:
    await call.answer("Готовлю развёрнутый ответ…")
    await run_llm(call.message, call.from_user.id, call.from_user.username, state, "Расскажи подробнее.", long=True)


@router.callback_query(Chat.active, F.data == "act:rewrite")
async def rewrite(call: CallbackQuery, state: FSMContext) -> None:
    await call.answer()
    await run_llm(
        call.message, call.from_user.id, call.from_user.username, state, "Дай другой вариант, иначе.", long=False
    )


@router.message(Chat.active, F.text)
async def scenario_message(message: Message, state: FSMContext) -> None:
    text = message.text
    if (await state.get_data()).get("scenario") == "competitors":
        text = await with_competitor_data(message, text)
    await run_llm(message, message.from_user.id, message.from_user.username, state, text, long=False)


async def with_competitor_data(message: Message, text: str) -> str:
    """Если в сообщении есть ссылки на конкурентов, дописывает к нему собранные с них данные."""
    sources = competitors.find_sources(text)
    if not sources:
        return text
    names = ", ".join(sanitize(s.target) for s in sources)
    await message.answer(f"🔎 Изучаю конкурентов: {names}\n<i>Это займёт до 20 секунд…</i>")
    await message.bot.send_chat_action(message.chat.id, ChatAction.TYPING)
    data = await competitors.collect(sources)
    return f"{text}\n\nДанные, которые бот собрал с открытых страниц конкурентов:\n{data}"


@router.message(F.text)
async def no_scenario(message: Message) -> None:
    await message.answer("👇 Выберите, с чем помочь:", reply_markup=main_menu())


async def run_llm(
    message: Message, user_id: int, username: str | None, state: FSMContext, text: str, long: bool
) -> None:
    async with Session() as session:
        user = await get_or_create_user(session, user_id, username)
        if user.requests_left <= 0:
            # TODO: оплата (Telegram Stars, ЮKassa, Freedom Pay)
            await message.answer("⏳ Бесплатные запросы закончились. Скоро здесь появятся тарифы.")
            return

        data = await state.get_data()
        scenario = SCENARIOS[data["scenario"]]
        system = "\n\n".join([
            BASE_PROMPT.format(profile=user.profile_text(), today=f"{date.today():%d.%m.%Y}"),
            f"Задача: {scenario.instruction}",
            LONG_MODE if long else SHORT_MODE,
        ])
        history = data.get("history", []) + [{"role": "user", "content": text}]

        await message.bot.send_chat_action(message.chat.id, ChatAction.TYPING)
        try:
            answer = await llm.ask(system, history, max_tokens=2500 if long else 800, web=scenario.web)
        except Exception:
            log.exception("LLM request failed")
            await message.answer("😔 Не получилось получить ответ, попробуйте ещё раз через минуту.")
            return

        user.requests_left -= 1
        await session.commit()

    history.append({"role": "assistant", "content": answer})
    await state.update_data(history=history[-HISTORY_LIMIT:])
    await send_answer(message, answer, after_answer(can_expand=not long))


async def send_answer(message: Message, answer: str, keyboard: InlineKeyboardMarkup) -> None:
    chunks = split(sanitize(answer))
    for i, chunk in enumerate(chunks):
        markup = keyboard if i == len(chunks) - 1 else None
        try:
            await message.answer(chunk, reply_markup=markup, link_preview_options=NO_PREVIEW)
        except TelegramBadRequest:
            # модель сломала разметку: отправляем тем же текстом, но без тегов
            await message.answer(strip_tags(chunk), reply_markup=markup, parse_mode=None)
