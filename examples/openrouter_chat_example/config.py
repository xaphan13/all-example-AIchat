"""Настройки примера.

Здесь показано, как читать ключ, адрес агрегатора и параметры запроса.
Настройки описаны один раз типизированно (`pydantic-settings`), берутся из
переменных окружения и, если рядом лежит `.env`, — ещё и оттуда.

Источник настроек — единственное, что меняется при переносе в другой проект.
Сам код клиента (`chat.py` и реализации) знать про него не должен: он получает
уже готовые значения.
"""

from __future__ import annotations

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Настройки доступа к агрегатору.

    Значения по умолчанию рассчитаны на OpenRouter: это его адрес и его
    формат заголовков атрибуции. Для другого агрегатора меняются `base_url`
    и, при необходимости, `app_url` / `app_title`.

    У каждого поля задан явный `alias` с именем переменной окружения:
    так видно, что именно читать в `.env`, и pydantic-settings не зависит
    от регистра и префиксов.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    # --- Доступ ---
    # Ключ обязателен: без него нет смысла запускать. Секрет живёт только
    # в окружении, в исходниках его быть не должно.
    api_key: str = Field(..., alias="OPENROUTER_API_KEY")
    base_url: str = Field("https://openrouter.ai/api/v1", alias="OPENROUTER_BASE_URL")
    model: str = Field("openai/gpt-4o-mini", alias="OPENROUTER_MODEL")

    # Резервные модели: чем подменить основную, если она откажет.
    # В окружении это строка через запятую, поэтому её разбирает валидатор ниже.
    # Тип объявлен как `str`, а не `tuple`, намеренно: для «сложных» типов
    # pydantic-settings сначала пытается разобрать значение как JSON и падает
    # на обычной строке, не дойдя до валидатора.
    fallback_models: str = Field("", alias="OPENROUTER_FALLBACK_MODELS")

    # --- Атрибуция в статистике агрегатора ---
    app_url: str = Field("http://localhost", alias="OPENROUTER_APP_URL")           # HTTP-Referer
    app_title: str = Field("OpenRouter Chat Example", alias="OPENROUTER_APP_TITLE")  # X-Title

    # --- Параметры запроса ---
    temperature: float = Field(0.7, alias="CHAT_TEMPERATURE")
    max_tokens: int = Field(1024, alias="CHAT_MAX_TOKENS")
    timeout_seconds: float = Field(60.0, alias="CHAT_TIMEOUT_SECONDS")

    # Какая реализация работает: "httpx" или "openai".
    backend: str = Field("httpx", alias="CHAT_BACKEND")

    @property
    def fallback_chain(self) -> tuple[str, ...]:
        """Основная модель и резервные одним кортежем: порядок попыток."""
        return (self.model, *self.fallback_models)

    @field_validator("fallback_models", mode="after")
    @classmethod
    def _split_models(cls, value: object) -> tuple[str, ...]:
        """Разобрать `OPENROUTER_FALLBACK_MODELS="a, b"` в кортеж имён."""
        if not isinstance(value, str):
            return tuple(value)  # type: ignore[arg-type]
        return tuple(name.strip() for name in value.split(",") if name.strip())
