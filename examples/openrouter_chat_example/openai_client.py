"""Реализация на официальном SDK OpenAI поверх агрегатора.

Тот же контракт `ChatClient`, что и у клиента на httpx, но вся работа с HTTP
и разбором SSE отдана SDK. Полезно, когда в проекте уже есть код на OpenAI SDK:
подключение агрегатора сводится к подмене `base_url`, ключа и заголовков.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from openai import AsyncOpenAI

from .chat import ChatClient, ChatMessage, ChatResult, Usage


class OpenAISDKChatClient(ChatClient):
    """Клиент агрегатора через `openai.AsyncOpenAI` с подменённым `base_url`."""

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        app_url: str = "http://localhost",
        app_title: str = "Chat Example",
        timeout_seconds: float = 60.0,
    ) -> None:
        self._client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url.rstrip("/"),
            # Заголовки атрибуции агрегатора: задаются один раз на весь клиент.
            default_headers={
                "HTTP-Referer": app_url,
                "X-Title": app_title,
            },
            timeout=timeout_seconds,
        )

    async def chat(
        self,
        messages: list[ChatMessage],
        *,
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> ChatResult:
        response = await self._client.chat.completions.create(
            model=model,
            messages=[m.as_dict() for m in messages],
            temperature=temperature,
            max_completion_tokens=max_tokens,
        )

        if not response.choices:
            raise RuntimeError(f"Ответ без choices, модель {model}")

        choice = response.choices[0]
        usage = response.usage

        return ChatResult(
            content=choice.message.content or "",
            model=response.model or model,
            usage=Usage(
                prompt_tokens=getattr(usage, "prompt_tokens", 0) or 0,
                completion_tokens=getattr(usage, "completion_tokens", 0) or 0,
            ),
            finish_reason=choice.finish_reason,
        )

    async def stream(
        self,
        messages: list[ChatMessage],
        *,
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> AsyncIterator[str]:
        """Поток текстовых фрагментов по мере генерации."""
        stream = await self._client.chat.completions.create(
            model=model,
            messages=[m.as_dict() for m in messages],
            temperature=temperature,
            max_completion_tokens=max_tokens,
            stream=True,
        )
        async for chunk in stream:
            for choice in chunk.choices or []:
                text = choice.delta.content
                if text:
                    yield text

    async def aclose(self) -> None:
        await self._client.close()
