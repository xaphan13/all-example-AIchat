"""Пример использования: один ответ, поток, fallback-модели.

Запуск (нужен только ключ, остальное имеет значения по умолчанию):

    export OPENROUTER_API_KEY=sk-or-...
    uv run python -m examples.openrouter_chat_example

Выбор реализации:

    CHAT_BACKEND=httpx   — прямая работа с HTTP (по умолчанию)
    CHAT_BACKEND=openai  — официальный SDK OpenAI поверх того же адреса
"""

from __future__ import annotations

import asyncio

from .chat import ChatClient, ChatMessage, ChatResult, create_client
from .config import Settings

QUESTION = "Объясни в трёх предложениях, что такое OpenAI-совместимый API."


def build_client(settings: Settings) -> ChatClient:
    """Собрать клиент из настроек. Один клиент на весь сценарий."""
    return create_client(
        settings.backend,
        api_key=settings.api_key,
        base_url=settings.base_url,
        app_url=settings.app_url,
        app_title=settings.app_title,
        timeout_seconds=settings.timeout_seconds,
    )


async def ask_once(client: ChatClient, settings: Settings) -> ChatResult:
    """Один запрос — один полный ответ."""
    return await client.chat(
        [ChatMessage(role="user", content=QUESTION)],
        model=settings.model,
        temperature=settings.temperature,
        max_tokens=settings.max_tokens,
    )


async def ask_with_fallback(client: ChatClient, settings: Settings) -> ChatResult:
    """Ответ с переходом на резервные модели.

    Порядок: основная модель, затем по очереди резервные из
    `OPENROUTER_FALLBACK_MODELS`. Резервные модели — самый простой способ
    пережить недоступность одной модели у агрегатора.
    """
    messages = [ChatMessage(role="user", content=QUESTION)]

    for model in settings.fallback_chain:
        try:
            return await client.chat(
                messages,
                model=model,
                temperature=settings.temperature,
                max_tokens=settings.max_tokens,
            )
        except Exception as error:  # noqa: BLE001 — в примере важно показать саму идею
            print(f"  модель {model} не ответила ({error}), пробую следующую")

    raise RuntimeError("Ни одна модель не ответила")


async def ask_streaming(client: ChatClient, settings: Settings) -> None:
    """Тот же вопрос, но с показом текста по мере генерации."""
    messages = [
        ChatMessage(role="system", content="Отвечай кратко и по делу."),
        ChatMessage(role="user", content=QUESTION),
    ]
    async for chunk in client.stream(
        messages,
        model=settings.model,
        temperature=settings.temperature,
        max_tokens=settings.max_tokens,
    ):
        print(chunk, end="", flush=True)
    print()


async def main() -> None:
    settings = Settings()
    client = build_client(settings)
    try:
        print("--- один запрос ---")
        result = await ask_once(client, settings)
        print(result.content)
        print(f"модель: {result.model}, токены: {result.usage.total_tokens}")

        if len(settings.fallback_chain) > 1:
            print("\n--- с fallback-моделями ---")
            answer = await ask_with_fallback(client, settings)
            print(f"ответила модель: {answer.model}")

        print("\n--- стриминг ---")
        await ask_streaming(client, settings)
    finally:
        await client.aclose()


if __name__ == "__main__":
    asyncio.run(main())
