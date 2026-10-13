# Офлайн-проверка сбора данных о конкурентах. Запуск: python tests/competitors_test.py
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.update(BOT_TOKEN="123:ABC", LLM_API_KEY="x")

from bot import competitors  # noqa: E402
from bot.competitors import Source, find_sources  # noqa: E402

# упрощённая копия разметки t.me/s/<канал>
TELEGRAM_HTML = """
<html><head><meta property="og:title" content="Кофе Рядом"></head><body>
<div class="tgme_channel_info_header_title"><span dir="auto">Кофе Рядом</span></div>
<div class="tgme_channel_info_description">Кофейня у метро.<br/>Завтраки навынос</div>
<div class="tgme_channel_info_counter"><span class="counter_value">12.4K</span> <span class="counter_type">subscribers</span></div>
<div class="tgme_widget_message_wrap"><div class="tgme_widget_message js-widget_message" data-post="coffee/9">
  <div class="tgme_widget_message_text js-message_text" dir="auto">Старый пост про лето</div>
  <div class="tgme_widget_message_footer"><span class="tgme_widget_message_views">900</span>
  <a class="tgme_widget_message_date"><time datetime="2025-12-01T09:00:00+00:00">Dec 1</time></a></div>
</div></div>
<div class="tgme_widget_message_wrap"><div class="tgme_widget_message js-widget_message" data-post="coffee/10">
  <div class="tgme_widget_message_photo_wrap"></div>
  <div class="tgme_widget_message_footer"><span class="tgme_widget_message_views">1.1K</span>
  <a class="tgme_widget_message_date"><time datetime="2026-10-01T09:00:00+00:00">Oct 1</time></a></div>
</div></div>
<div class="tgme_widget_message_wrap"><div class="tgme_widget_message js-widget_message" data-post="coffee/11">
  <div class="tgme_widget_message_text js-message_text" dir="auto">Скидка <b>20%</b> на капучино<br/>до пятницы!</div>
  <div class="tgme_widget_message_footer"><span class="tgme_widget_message_views">3.5K</span>
  <a class="tgme_widget_message_date"><time datetime="2026-10-05T09:00:00+00:00">Oct 5</time></a></div>
</div></div>
</body></html>
"""

SITE_HTML = """<html><head><title>Кофе Рядом — кофейня</title><meta name="description" content="Лучший кофе района">
<script>var x = "не текст";</script></head><body><h1>Кофе с собой за 3 минуты</h1>
<p>Капучино 250 ₽, раф 300 руб. Завтрак от 390 ₽.</p></body></html>"""


def test_find_sources():
    text = "вот: https://t.me/coffee_rival, @another_cafe, t.me/s/third, vk.com/cafe_club и coffee.kz/menu"
    got = [(s.kind, s.target) for s in find_sources(text)]
    assert got == [("telegram", "another_cafe"), ("telegram", "coffee_rival"), ("telegram", "third")], got
    got = [(s.kind, s.target) for s in find_sources("vk.com/cafe_club и https://coffee.kz/menu")]
    assert got == [("vk", "cafe_club"), ("site", "https://coffee.kz/menu")], got
    assert find_sources("просто кофейня у метро, без ссылок") == []
    assert [s.kind for s in find_sources("почта info@coffee.ru")] == []


async def fake_get_text(http, url, redirects_left=3):
    return TELEGRAM_HTML if "t.me/s/" in url else SITE_HTML


async def test_collect():
    competitors._get_text = fake_get_text

    async def public(url):
        return None
    real_ensure = competitors._ensure_public
    competitors._ensure_public = public
    out = await competitors.collect([Source("telegram", "coffee"), Source("site", "https://coffee.kz")])
    print(out)
    assert "Подписчики: 12.4K" in out
    assert "2026-10-05 | 3.5K | Скидка 20% на капучино до пятницы!" in out
    assert "2026-10-01 | 1.1K | (фото/видео без текста)" in out
    assert "Старый пост" not in out  # старше 6 месяцев
    assert "Кофе с собой за 3 минуты" in out and "250 ₽" in out and "не текст" not in out
    assert "VK не подключён" in await competitors._collect_one(None, Source("vk", "cafe"))

    # бот не должен ходить во внутреннюю сеть по ссылке пользователя
    competitors._ensure_public = real_ensure
    for url in ["http://127.0.0.1:8080/admin", "http://localhost/", "http://169.254.169.254/latest", "file:///etc/passwd"]:
        assert "Не удалось получить данные" in await competitors._collect_one(None, Source("site", url)), url


test_find_sources()
asyncio.run(test_collect())
print("OK")
