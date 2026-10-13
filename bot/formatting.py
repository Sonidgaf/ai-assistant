import html
import re

TELEGRAM_LIMIT = 4096
# теги, которые Telegram понимает и которые мы разрешаем модели
_ALLOWED = re.compile(r"&lt;(/?)(b|i|u|s|code|blockquote)&gt;")
_MARKDOWN_BOLD = re.compile(r"\*\*(.+?)\*\*")
_MARKDOWN_LINK = re.compile(r"\[([^\]\n]{1,100})\]\((https?://[^\s)\"<>]+)\)")


def sanitize(text: str) -> str:
    """Экранирует всё, кроме разрешённых тегов, чтобы случайный «<» от модели не ломал сообщение."""
    text = _MARKDOWN_BOLD.sub(r"<b>\1</b>", text)  # модель иногда всё же пишет **жирный**
    text = _ALLOWED.sub(r"<\1\2>", html.escape(text, quote=False))
    # ссылки на источники из поиска: [vc.ru](https://...) -> кликабельное название
    return _MARKDOWN_LINK.sub(lambda m: f'<a href="{m.group(2)}">{m.group(1)}</a>', text)


def strip_tags(text: str) -> str:
    return html.unescape(re.sub(r"</?[a-z]+(?: [^>]*)?>", "", text))


def split(text: str, limit: int = TELEGRAM_LIMIT) -> list[str]:
    """Режет длинный ответ по абзацам, чтобы не разрывать теги посередине."""
    chunks, current = [], ""
    for paragraph in text.split("\n\n"):
        candidate = f"{current}\n\n{paragraph}" if current else paragraph
        if len(candidate) <= limit:
            current = candidate
            continue
        if current:
            chunks.append(current)
        while len(paragraph) > limit:
            chunks.append(paragraph[:limit])
            paragraph = paragraph[limit:]
        current = paragraph
    if current:
        chunks.append(current)
    return chunks
