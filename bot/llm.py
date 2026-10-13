from datetime import date

from openai import AsyncOpenAI

from bot.config import settings

client = AsyncOpenAI(api_key=settings.llm_api_key, base_url=settings.llm_base_url)


def search_prompt() -> str:
    return (
        f"Свежие результаты поиска в интернете (сегодня {date.today():%d.%m.%Y}). "
        "Опирайся прежде всего на материалы за последние 4–6 месяцев; более старые используй только "
        "с пометкой даты. Ссылайся на источники markdown-ссылкой с названием домена, например [vc.ru](https://vc.ru/...):"
    )


async def ask(system: str, messages: list[dict], max_tokens: int = 800, web: bool = False) -> str:
    extra = {}
    if web and settings.web_search:
        extra["plugins"] = [{"id": "web", "max_results": settings.web_results, "search_prompt": search_prompt()}]
    response = await client.chat.completions.create(
        model=settings.llm_model,
        messages=[{"role": "system", "content": system}, *messages],
        max_tokens=max_tokens,
        extra_body=extra or None,
    )
    return response.choices[0].message.content or ""
