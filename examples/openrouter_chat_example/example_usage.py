"""Пример использования: один ответ, поток, fallback-модели.

Запуск (нужен только ключ, остальное имеет дефолты):

    export OPENROUTER_API_KEY=sk-or-...
    uv run python -m examples.openrouter_chat_example.example_usage

Выбор реализации:

    CHAT_BACKEND=httpx   — прямая работа с HTTP (по умолчанию)
    CHAT_BACKEND=openai  — официальный SDK OpenAI поверх того же адреса
"""

from __future__ import annotations

import asyncio
import logging

from .chat import ChatMessage, ChatResult, ProviderError, create_client
from .config import Settings

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


async def ask_once(settings: Settings, question: str) -> ChatResult:
    """Один запрос — один полный ответ."""
    client = create_client(
        settings.backend,
        api_key=settings.api_key,
        base_url=settings.base_url,
        app_url=settings.app_url,
        app_title=settings.app_title,
        timeout_seconds=settings.timeout_seconds,
        max_retries=settings.max_retries,
    )
    try:
        return await client.chat(
            [ChatMessage(role="user", content=question)],
            model=settings.model,
            temperature=settings.temperature,
            max_tokens=settings.max_tokens,
        )
    finally:
        await client.aclose()


async def ask_streaming(settings: Settings, question: str) -> None:
    """Тот же вопрос, но с показом текста по мере генерации."""
    client = create_client(
        settings.backend,
        api_key=settings.api_key,
        base_url=settings.base_url,
        app_url=settings.app_url,
        app_title=settings.app_title,
        timeout_seconds=settings.timeout_seconds,
        max_retries=settings.max_retries,
    )
    try:
        messages = [
            ChatMessage(role="system", content="Отвечай кратко и по делу."),
            ChatMessage(role="user", content=question),
        ]
        async for item in client.stream_with_usage(
            messages,
            model=settings.model,
            temperature=settings.temperature,
            max_tokens=settings.max_tokens,
        ):
            if isinstance(item, str):
                print(item, end="", flush=True)
            else:
                print(f"\n[токены: {item.prompt_tokens} + {item.completion_tokens}]")
    finally:
        await client.aclose()


async def ask_with_fallback(settings: Settings, question: str) -> ChatResult:
    """Ответ с переходом на резервные модели.

    Порядок попыток: основная модель, затем по очереди резервные из
    `OPENROUTER_FALLBACK_MODELS`. Переход выполняется только на повторяемых
    отказах — если провайдер ответил 400, это ошибка запроса, а не повод
    менять модель.
    """
    client = create_client(
        settings.backend,
        api_key=settings.api_key,
        base_url=settings.base_url,
        app_url=settings.app_url,
        app_title=settings.app_title,
        timeout_seconds=settings.timeout_seconds,
        max_retries=settings.max_retries,
    )
    chain = (settings.model, *settings.fallback_models)
    last_error: ProviderError | None = None

    try:
        for model in chain:
            try:
                return await client.chat(
                    [ChatMessage(role="user", content=question)],
                    model=model,
                    temperature=settings.temperature,
                    max_tokens=settings.max_tokens,
                )
            except ProviderError as error:
                last_error = error
                if not error.retryable:
                    raise
                logging.getLogger(__name__).warning(
                    "Модель %s недоступна (%s), перехожу к следующей", model, error
                )
    finally:
        await client.aclose()

    raise last_error or ProviderError("Ни одна модель не ответила")


async def main() -> None:
    settings = Settings.from_env()
    question = "Объясни в трёх предложениях, что такое OpenAI-совместимый API."

    result = await ask_once(settings, question)
    print("--- один запрос ---")
    print(result.content)
    print(f"модель: {result.model}, токены: {result.usage.total_tokens}")

    if settings.fallback_models:
        print("\n--- с fallback-моделями ---")
        answer = await ask_with_fallback(settings, question)
        print(f"ответила модель: {answer.model}")

    print("\n--- стриминг ---")
    await ask_streaming(settings, question)


if __name__ == "__main__":
    asyncio.run(main())
