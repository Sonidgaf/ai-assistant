# Офлайн-проверка всего сценария: фейковый Telegram и фейковая модель. Запуск: python tests/smoke_test.py
import asyncio, os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.update(BOT_TOKEN="123:ABC", LLM_API_KEY="x", DATABASE_URL="sqlite+aiosqlite:///" + os.path.join(tempfile.mkdtemp(), "bot.db") + "", ADMIN_IDS="1")
from datetime import datetime
from aiogram import Bot, Dispatcher
from aiogram.types import Update, Message, User, Chat, CallbackQuery
from bot import competitors, llm
from bot.db import init_db
from bot.handlers import admin, onboarding, scenarios

sent = []
class FakeBot(Bot):
    async def __call__(self, method, request_timeout=None):
        sent.append((type(method).__name__, getattr(method, "text", None)))
        return True

async def fake_ask(system, messages, max_tokens=800, web=False):
    assert "Сегодня " in system and "4–6 месяцев" in system
    web_calls.append(web)
    assert "Тон бренда: Экспертный" in system, system
    mode = "ПОДРОБНО" if "ПОДРОБНО" in system else "КОРОТКО"
    # модель может прислать «<» и **markdown**: бот должен это пережить
    return f"🔥 **{mode}** ответ на: {messages[-1]['content']} (история {len(messages)}) 5 < 7 <b>ok</b>"
llm.ask = fake_ask
web_calls = []

async def fake_collect(sources):
    return "=== telegram: coffee_rival ===\nПодписчики: 5K"
competitors.collect = fake_collect

u = User(id=1, is_bot=False, first_name="R")
c = Chat(id=1, type="private")
n = 0
def msg(text):
    global n; n += 1
    return Update(update_id=n, message=Message(message_id=n, date=datetime.now(), chat=c, from_user=u, text=text))
def cb(data):
    global n; n += 1
    return Update(update_id=n, callback_query=CallbackQuery(id=str(n), from_user=u, chat_instance="x", data=data,
        message=Message(message_id=n, date=datetime.now(), chat=c, from_user=u, text="..")))

async def main():
    await init_db()
    from aiogram.client.default import DefaultBotProperties
    bot = FakeBot("123:ABC", default=DefaultBotProperties(parse_mode="HTML")); dp = Dispatcher()
    dp.include_routers(admin.router, onboarding.router, scenarios.router)
    for up in [msg("/start"), cb("bt:1"), msg("Кофейня в Казани"), msg("Студенты 18-25"), msg("Telegram, VK"),
               cb("tone:1"), cb("sc:competitors"), msg("t.me/coffee_rival"), cb("act:more"), cb("act:menu"),
               cb("sc:post"), cb("ex:0"), cb("act:rewrite"), cb("act:menu"),
               msg("привет"), msg("/stats")]:
        await dp.feed_update(bot, up)
    for s in sent:
        print(s[0], "|", (s[1] or "")[:90].replace("\n", " "))
asyncio.run(main())
# анализ конкурентов и «Подробнее» ищут в интернете, пост пишется без поиска
assert web_calls == [True, True, False, False], web_calls
assert any("Изучаю конкурентов: coffee_rival" in (t or "") for _, t in sent)
