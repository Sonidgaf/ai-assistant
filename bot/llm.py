from openai import AsyncOpenAI

from bot.config import settings

client = AsyncOpenAI(api_key=settings.llm_api_key, base_url=settings.llm_base_url)


async def ask(system: str, messages: list[dict], max_tokens: int = 800) -> str:
    response = await client.chat.completions.create(
        model=settings.llm_model,
        messages=[{"role": "system", "content": system}, *messages],
        max_tokens=max_tokens,
    )
    return response.choices[0].message.content or ""
