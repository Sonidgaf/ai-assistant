import html
import re

TELEGRAM_LIMIT = 4096
# теги, которые Telegram понимает и которые мы разрешаем модели
_ALLOWED = re.compile(r"&lt;(/?)(b|i|u|s|code|blockquote)&gt;")
_MARKDOWN_BOLD = re.compile(r"\*\*(.+?)\*\*")


def sanitize(text: str) -> str:
    """Экранирует всё, кроме разрешённых тегов, чтобы случайный «<» от модели не ломал сообщение."""
    text = _MARKDOWN_BOLD.sub(r"<b>\1</b>", text)  # модель иногда всё же пишет **жирный**
    return _ALLOWED.sub(r"<\1\2>", html.escape(text, quote=False))


def strip_tags(text: str) -> str:
    return html.unescape(re.sub(r"</?[a-z]+>", "", text))


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
