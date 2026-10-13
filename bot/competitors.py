"""Сбор открытых данных о конкурентах по ссылкам: Telegram-канал, VK-сообщество, сайт."""

import asyncio
import ipaddress
import logging
import re
import socket
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from html.parser import HTMLParser
from urllib.parse import urlparse

import aiohttp
from yarl import URL

from bot.config import settings

log = logging.getLogger(__name__)

MAX_COMPETITORS = 3
MAX_PAGE_BYTES = 1_500_000
MAX_SUMMARY_CHARS = 5000
TIMEOUT = aiohttp.ClientTimeout(total=15)
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; MarketerBot/1.0)", "Accept-Language": "ru,en;q=0.8"}

_URL = re.compile(r"(?<![@\w.])(?:https?://)?(?:www\.)?[a-z0-9][a-z0-9.-]*\.[a-z]{2,}(?:/[^\s,;]*)?", re.IGNORECASE)
_MENTION = re.compile(r"(?<![\w.])@([a-z][a-z0-9_]{3,31})\b", re.IGNORECASE)
_PRICE = re.compile(r"[^.\n]{0,60}\d[\d\s.,]*\s?(?:₽|руб|сом|тг|₸|\$|usd|eur|€)[^.\n]{0,40}", re.IGNORECASE)


@dataclass
class Source:
    kind: str  # telegram | vk | site
    target: str  # имя канала / домен сообщества / url


def find_sources(text: str) -> list[Source]:
    sources: list[Source] = []
    for name in _MENTION.findall(text):
        sources.append(Source("telegram", name))
    for raw in _URL.findall(text):
        url = raw if raw.lower().startswith("http") else f"https://{raw}"
        parsed = urlparse(url)
        host = parsed.netloc.lower().removeprefix("www.")
        path = parsed.path.strip("/").split("/")
        if host in {"t.me", "telegram.me"} and path and path[0]:
            name = path[1] if path[0] == "s" and len(path) > 1 else path[0]
            sources.append(Source("telegram", name))
        elif host in {"vk.com", "vk.ru", "m.vk.com"} and path and path[0]:
            sources.append(Source("vk", path[0]))
        elif "@" not in raw:
            sources.append(Source("site", url))
    unique, seen = [], set()
    for s in sources:
        key = (s.kind, s.target.lower())
        if key not in seen:
            seen.add(key)
            unique.append(s)
    return unique[:MAX_COMPETITORS]


async def collect(sources: list[Source]) -> str:
    """Возвращает текстовую сводку по всем источникам для передачи модели."""
    async with aiohttp.ClientSession(timeout=TIMEOUT, headers=HEADERS) as http:
        results = await asyncio.gather(*(_collect_one(http, s) for s in sources))
    return "\n\n".join(results)


async def _collect_one(http: aiohttp.ClientSession, source: Source) -> str:
    try:
        if source.kind == "telegram":
            summary = await _telegram(http, source.target)
        elif source.kind == "vk":
            summary = await _vk(http, source.target)
        else:
            summary = await _site(http, source.target)
    except Exception as e:  # сеть, таймаут, неожиданная разметка: не роняем весь анализ
        log.warning("competitor fetch failed for %s: %r", source, e)
        summary = "Не удалось получить данные (страница недоступна или закрыта)."
    return f"=== {source.kind}: {source.target} ===\n{summary[:MAX_SUMMARY_CHARS]}"


# --- Telegram -----------------------------------------------------------------

class _TelegramParser(HTMLParser):
    """Разбирает публичную веб-версию канала t.me/s/<канал>."""

    VOID = {"br", "img", "meta", "link", "input", "hr", "source", "wbr"}
    CHANNEL_FIELDS = {
        "tgme_channel_info_header_title": "title",
        "tgme_channel_info_description": "description",
        "counter_value": "counter",
    }
    POST_FIELDS = {"tgme_widget_message_text": "text", "tgme_widget_message_views": "views"}

    def __init__(self) -> None:
        super().__init__()
        self.channel: dict[str, list[str]] = {v: [] for v in self.CHANNEL_FIELDS.values()}
        self.posts: list[dict[str, str]] = []
        self._field: tuple[str, str] | None = None  # (куда, поле)
        self._depth = 0
        self._buf: list[str] = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "br" and self._field:
            self._buf.append("\n")
        if tag in self.VOID:
            return
        if self._field:
            self._depth += 1
            return
        classes = (attrs.get("class") or "").split()
        if "tgme_widget_message" in classes and attrs.get("data-post"):
            self.posts.append({})
        if tag == "time" and attrs.get("datetime") and self.posts:
            self.posts[-1].setdefault("date", attrs["datetime"][:10])
        for cls, field in self.CHANNEL_FIELDS.items():
            if cls in classes:
                self._start(("channel", field))
                return
        for cls, field in self.POST_FIELDS.items():
            if cls in classes and self.posts and field not in self.posts[-1]:
                self._start(("post", field))
                return

    def _start(self, field: tuple[str, str]) -> None:
        self._field, self._depth, self._buf = field, 1, []

    def handle_endtag(self, tag):
        if not self._field or tag in self.VOID:
            return
        self._depth -= 1
        if self._depth == 0:
            where, name = self._field
            value = "".join(self._buf).strip()
            if where == "channel":
                self.channel[name].append(value)
            else:
                self.posts[-1][name] = value
            self._field = None

    def handle_data(self, data):
        if self._field:
            self._buf.append(data)


async def _telegram(http: aiohttp.ClientSession, channel: str) -> str:
    html = await _get_text(http, f"https://t.me/s/{channel}")
    p = _TelegramParser()
    p.feed(html)
    if not p.posts and not p.channel["title"]:
        return "Канал не найден, закрыт или у него нет публичной веб-версии."
    fresh = [post for post in p.posts if _is_fresh(post.get("date"))]
    posts = fresh[-15:]
    dates = [post["date"] for post in posts if post.get("date")]
    lines = [
        f"Название: {_first(p.channel['title'])}",
        f"Описание: {_short(_first(p.channel['description']), 400)}",
        f"Подписчики: {_first(p.channel['counter'])}",
    ]
    if dates:
        lines.append(f"Последние {len(posts)} постов опубликованы с {dates[0]} по {dates[-1]}")
    elif p.posts:
        last = next((post["date"] for post in reversed(p.posts) if post.get("date")), "?")
        lines.append(f"За последние 6 месяцев постов нет, последний пост: {last}. Канал, похоже, заброшен.")
    lines.append("Посты (дата | просмотры | текст):")
    for post in posts:
        text = _short(post.get("text", ""), 280) or "(фото/видео без текста)"
        lines.append(f"- {post.get('date', '?')} | {post.get('views', '?')} | {text}")
    return "\n".join(lines)


# --- VK -----------------------------------------------------------------------

async def _vk(http: aiohttp.ClientSession, domain: str) -> str:
    if not settings.vk_token:
        return "VK не подключён (нет VK_TOKEN), данные сообщества недоступны."
    base = {"access_token": settings.vk_token, "v": "5.199"}
    async with http.get("https://api.vk.com/method/groups.getById",
                        params={**base, "group_id": domain, "fields": "description,members_count"}) as r:
        info = (await r.json()).get("response", {})
    group = (info.get("groups") if isinstance(info, dict) else info) or [{}]
    async with http.get("https://api.vk.com/method/wall.get", params={**base, "domain": domain, "count": 20}) as r:
        wall = (await r.json()).get("response", {}).get("items", [])
    lines = [
        f"Название: {group[0].get('name', '?')}",
        f"Описание: {_short(group[0].get('description', ''), 400)}",
        f"Участники: {group[0].get('members_count', '?')}",
        "Последние посты (лайки/просмотры | текст):",
    ]
    fresh = [item for item in wall if _is_fresh(datetime.fromtimestamp(item.get("date", 0)).date().isoformat())]
    if not fresh and wall:
        lines.append("За последние 6 месяцев постов нет, сообщество, похоже, неактивно.")
    for item in fresh[:15]:
        likes = item.get("likes", {}).get("count", "?")
        views = item.get("views", {}).get("count", "?")
        day = datetime.fromtimestamp(item.get("date", 0)).date().isoformat()
        lines.append(f"- {day} [{likes}/{views}] {_short(item.get('text', ''), 280)}")
    return "\n".join(lines)


# --- Сайт ---------------------------------------------------------------------

class _SiteParser(HTMLParser):
    SKIP = {"script", "style", "noscript", "svg", "template"}

    def __init__(self) -> None:
        super().__init__()
        self.title = ""
        self.description = ""
        self.headings: list[str] = []
        self.text: list[str] = []
        self._skip = 0
        self._tag = ""

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        self._tag = tag
        if tag in self.SKIP:
            self._skip += 1
        if tag == "meta" and (attrs.get("name") or attrs.get("property") or "").lower() in {
            "description", "og:description"
        }:
            self.description = self.description or (attrs.get("content") or "")

    def handle_endtag(self, tag):
        if tag in self.SKIP and self._skip:
            self._skip -= 1

    def handle_data(self, data):
        data = " ".join(data.split())
        if not data or self._skip:
            return
        if self._tag == "title" and not self.title:
            self.title = data
        elif self._tag in {"h1", "h2", "h3"}:
            self.headings.append(data)
        self.text.append(data)


async def _site(http: aiohttp.ClientSession, url: str) -> str:
    await _ensure_public(url)
    html = await _get_text(http, url)
    p = _SiteParser()
    p.feed(html)
    body = " ".join(p.text)
    prices = list(dict.fromkeys(m.strip() for m in _PRICE.findall(body)))[:10]
    return "\n".join([
        f"Заголовок: {p.title}",
        f"Описание: {p.description}",
        "Заголовки на странице: " + " | ".join(p.headings[:20]),
        "Упоминания цен: " + (" | ".join(prices) if prices else "не найдены"),
        f"Текст страницы (начало): {_short(body, 2500)}",
    ])


# --- общее --------------------------------------------------------------------

async def _ensure_public(url: str) -> None:
    """Не даём боту ходить во внутреннюю сеть сервера по ссылке от пользователя."""
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("unsupported url")
    infos = await asyncio.get_running_loop().getaddrinfo(parsed.hostname, parsed.port or 443, type=socket.SOCK_STREAM)
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if not ip.is_global:
            raise ValueError(f"non-public address {ip}")


async def _get_text(http: aiohttp.ClientSession, url: str, redirects_left: int = 3) -> str:
    # редиректы проверяем сами: иначе внешний сайт может перенаправить бота на внутренний адрес
    async with http.get(url, allow_redirects=False) as r:
        if r.status in {301, 302, 303, 307, 308} and r.headers.get("Location"):
            if redirects_left == 0:
                raise ValueError("too many redirects")
            location = str(r.url.join(URL(r.headers["Location"])))
            await _ensure_public(location)
            return await _get_text(http, location, redirects_left - 1)
        r.raise_for_status()
        raw = await r.content.read(MAX_PAGE_BYTES)
        return raw.decode(r.charset or "utf-8", errors="replace")


def _is_fresh(day: str | None) -> bool:
    """Пост моложе settings.fresh_days (≈6 месяцев). Посты без даты считаем свежими."""
    if not day:
        return True
    try:
        return date.fromisoformat(day) >= date.today() - timedelta(days=settings.fresh_days)
    except ValueError:
        return True


def _first(items: list[str]) -> str:
    return items[0] if items else "?"


def _short(text: str, limit: int) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[:limit] + "…"
