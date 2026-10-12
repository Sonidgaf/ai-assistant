# AI-маркетолог (Telegram-бот)

Каркас MVP: анкета при старте, 6 сценариев (контент-план, пост, УТП, реклама, анализ конкурентов, свободный вопрос),
память диалога внутри сценария, кнопки «Переписать» / «Короче», бесплатный лимит запросов, /stats для админа.

## Запуск локально

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # вписать BOT_TOKEN и LLM_API_KEY
python -m bot
```

## Команды бота
- /start — анкета или главное меню
- /profile — заново заполнить анкету
- /stats — число пользователей (только для ADMIN_IDS)

## Дальше по плану
- сбор реальных данных конкурентов (t.me/s/<канал>, сайт, VK)
- оплата: Telegram Stars + ЮKassa
- рефералка, рассылка

## Проверка

```bash
python tests/smoke_test.py
```
