from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    bot_token: str
    llm_api_key: str
    llm_base_url: str = "https://openrouter.ai/api/v1"
    llm_model: str = "anthropic/claude-sonnet-4.5"
    database_url: str = "sqlite+aiosqlite:///bot.db"
    free_requests: int = 10
    admin_ids: str = ""
    vk_token: str = ""
    web_search: bool = True  # поиск в интернете через OpenRouter, ~0.02 $ за запрос
    web_results: int = 5
    fresh_days: int = 183  # насколько свежими должны быть данные (≈6 месяцев)  # сервисный ключ VK-приложения, нужен для анализа VK-сообществ

    @property
    def admins(self) -> set[int]:
        return {int(x) for x in self.admin_ids.split(",") if x.strip()}


settings = Settings()
