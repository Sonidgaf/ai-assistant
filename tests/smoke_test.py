# Офлайн-проверка всего сценария: фейковый Telegram и фейковая модель. Запуск: python tests/smoke_test.py
import asyncio, os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.update(BOT_TOKEN="123:ABC", LLM_API_KEY="x", DATABASE_URL="sqlite+aiosqlite:///" + os.path.join(tempfile.mkdtemp(), "bot.db") + "", ADMIN_IDS="1")
from datetime import datetime
from aiogram import Bot, Dispatcher
from aiogram.types import Update, Message, User, Chat, CallbackQuery
from bot import llm
from bot.db import init_db
from bot.handlers import admin, onboarding, scenarios

sent = []
class FakeBot(Bot):
    async def __call__(self, method, request_timeout=None):
        sent.append((type(method).__name__, getattr(method, "text", None)))
        return True

async def fake_ask(system, messages):
    assert "Тон бренда: Экспертный" in system, system
    return f"ОТВЕТ на: {messages[-1]['content']} (история {len(messages)})"
llm.ask = fake_ask

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
    bot = FakeBot("123:ABC"); dp = Dispatcher()
    dp.include_routers(admin.router, onboarding.router, scenarios.router)
    for up in [msg("/start"), cb("bt:1"), msg("Кофейня в Казани"), msg("Студенты 18-25"), msg("Telegram, VK"),
               cb("tone:1"), cb("sc:competitors"), msg("t.me/coffee_rival"), cb("act:shorter"), cb("act:menu"),
               msg("привет"), msg("/stats")]:
        await dp.feed_update(bot, up)
    for s in sent:
        if s[1]: print(s[0], "|", s[1][:90].replace("\n", " "))
asyncio.run(main())
