"""Пример чтения настроек.

Показывает, откуда берутся ключ, адрес агрегатора и параметры повторов.
В реальном проекте это место заменяется на ваш конфиг (pydantic-settings,
Django settings, переменные окружения и т. п.) — остальной код не меняется.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError as error:
        raise ValueError(f"{name} должно быть целым числом, получено {raw!r}") from error


@dataclass(frozen=True, slots=True)
class Settings:
    """Настройки доступа к агрегатору.

    Значения по умолчанию рассчитаны на OpenRouter: это его адрес и его формат
    заголовков. Для другого агрегатора меняются только `base_url` и, при
    необходимости, `app_url` / `app_title`.
    """

    backend: str          # какой реализацией работать: "httpx" или "openai"
    api_key: str          # ключ агрегатора
    base_url: str         # адрес OpenAI-совместимого входа
    model: str            # модель в формате вендор/модель, например "openai/gpt-4o-mini"
    fallback_models: tuple[str, ...]  # чем подменить модель, если основная отказала

    app_url: str          # HTTP-Referer: атрибуция приложения в статистике агрегатора
    app_title: str        # X-Title: имя приложения в статистике агрегатора

    timeout_seconds: float
    max_retries: int      # число повторов на 429 и 5xx
    retry_backoff_seconds: float  # база экспоненциального backoff

    temperature: float
    max_tokens: int

    @classmethod
    def from_env(cls) -> "Settings":
        """Собрать настройки из окружения, не подставляя секреты в код."""
        api_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
        if not api_key:
            raise RuntimeError(
                "Не задан OPENROUTER_API_KEY. Ключ должен приходить из окружения "
                "или секрет-менеджера, а не храниться в исходниках."
            )

        raw_fallbacks = os.getenv("OPENROUTER_FALLBACK_MODELS", "")
        fallback_models = tuple(m.strip() for m in raw_fallbacks.split(",") if m.strip())

        return cls(
            backend=os.getenv("CHAT_BACKEND", "httpx"),
            api_key=api_key,
            base_url=os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
            model=os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini"),
            fallback_models=fallback_models,
            app_url=os.getenv("OPENROUTER_APP_URL", "http://localhost"),
            app_title=os.getenv("OPENROUTER_APP_TITLE", "OpenRouter Chat Example"),
            timeout_seconds=float(os.getenv("CHAT_TIMEOUT_SECONDS", "60")),
            max_retries=_env_int("CHAT_MAX_RETRIES", 3),
            retry_backoff_seconds=float(os.getenv("CHAT_RETRY_BACKOFF_SECONDS", "0.5")),
            temperature=float(os.getenv("CHAT_TEMPERATURE", "0.7")),
            max_tokens=_env_int("CHAT_MAX_TOKENS", 1024),
        )
