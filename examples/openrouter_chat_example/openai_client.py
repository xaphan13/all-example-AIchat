"""Реализация на официальном SDK OpenAI поверх агрегатора.

Тот же контракт, что и у клиента на httpx, но вся работа с HTTP, повторами и
разбором SSE отдана SDK. Полезно, когда в проекте уже есть код на OpenAI SDK:
подключение агрегатора сводится к подмене `base_url`, ключа и заголовков.

Пакет: `pip install openai` (требуется Python 3.10+).
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator

from openai import AsyncOpenAI, APIConnectionError, APIStatusError, APITimeoutError

from .chat import ChatClient, ChatMessage, ChatResult, ProviderError, Usage

logger = logging.getLogger(__name__)

# Коды, которые агрегатор отдаёт при перегрузке и лимитах — их имеет смысл повторять.
RETRYABLE_STATUS_CODES = frozenset({408, 409, 425, 429, 500, 502, 503, 504})


class OpenAISDKChatClient(ChatClient):
    """Клиент агрегатора через `openai.AsyncOpenAI` с подменённым `base_url`.

    Важно про повторы: SDK сам повторяет запросы на 429/5xx и сетевые ошибки
    (`max_retries`, по умолчанию 2) с коротким экспоненциальным backoff. Поэтому
    свой цикл повторов здесь не нужен — иначе попытки перемножатся.
    """

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        app_url: str = "http://localhost",
        app_title: str = "Chat Example",
        timeout_seconds: float = 60.0,
        max_retries: int = 3,
    ) -> None:
        self._max_retries = max_retries
        self._client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url.rstrip("/"),
            # Заголовки атрибуции агрегатора. В конструкторе ChatOpenAI их нет,
            # а здесь они задаются на весь клиент, а не на каждый вызов.
            default_headers={
                "HTTP-Referer": app_url,
                "X-Title": app_title,
            },
            timeout=timeout_seconds,
            max_retries=max_retries,
        )

    async def chat(
        self,
        messages: list[ChatMessage],
        *,
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> ChatResult:
        try:
            response = await self._client.chat.completions.create(
                model=model,
                messages=[_as_sdk_message(m) for m in messages],
                temperature=temperature,
                max_completion_tokens=max_tokens,
            )
        except (APIStatusError, APIConnectionError, APITimeoutError) as error:
            raise _as_provider_error(error, model) from error

        if not response.choices:
            raise ProviderError("Ответ без choices", model=model)

        choice = response.choices[0]
        usage = response.usage

        return ChatResult(
            content=choice.message.content or "",
            model=response.model or model,
            usage=Usage(
                prompt_tokens=getattr(usage, "prompt_tokens", 0) or 0,
                completion_tokens=getattr(usage, "completion_tokens", 0) or 0,
            ),
            provider=None,  # SDK отдаёт полезную нагрузку чанка как есть, без поля provider
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
        """Поток текста.

        Расход токенов здесь не отдаётся: при стриминге часть агрегаторов
        возвращает usage только в последнем чанке, и чтобы его получить,
        в запрос добавляется `stream_options={"include_usage": True}`.
        Пример разбора — в `stream_with_usage`.
        """
        async for item in self.stream_with_usage(
            messages, model=model, temperature=temperature, max_tokens=max_tokens
        ):
            if isinstance(item, str):
                yield item

    async def stream_with_usage(
        self,
        messages: list[ChatMessage],
        *,
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> AsyncIterator[str | Usage]:
        """Поток текста, последним элементом — расход токенов."""
        try:
            stream = await self._client.chat.completions.create(
                model=model,
                messages=[_as_sdk_message(m) for m in messages],
                temperature=temperature,
                max_completion_tokens=max_tokens,
                stream=True,
                stream_options={"include_usage": True},
            )
        except (APIStatusError, APIConnectionError, APITimeoutError) as error:
            raise _as_provider_error(error, model) from error

        usage_yielded = False
        async for chunk in stream:
            # Чанк с usage может не содержать choices — это нормально.
            if chunk.usage is not None:
                yield Usage(
                    prompt_tokens=chunk.usage.prompt_tokens or 0,
                    completion_tokens=chunk.usage.completion_tokens or 0,
                )
                usage_yielded = True

            for choice in chunk.choices or []:
                text = choice.delta.content
                if text:
                    yield text

        if not usage_yielded:
            logger.debug("Агрегатор не вернул usage для потокового ответа")

    async def aclose(self) -> None:
        await self._client.close()


def _as_sdk_message(message: ChatMessage) -> dict[str, str]:
    """Сообщение в том виде, который ждёт SDK (обычный словарь)."""
    return message.as_dict()


def _as_provider_error(error: Exception, model: str) -> ProviderError:
    """Привести исключения SDK к общему `ProviderError`."""
    if isinstance(error, APIStatusError):
        retryable = error.status_code in RETRYABLE_STATUS_CODES
        return ProviderError(
            f"Агрегатор вернул {error.status_code}: {error.message}",
            status_code=error.status_code,
            model=model,
            retryable=retryable,
        )
    if isinstance(error, APITimeoutError):
        return ProviderError(f"Таймаут запроса к агрегатору: {error}", model=model, retryable=True)
    return ProviderError(f"Сетевая ошибка при запросе к агрегатору: {error}", model=model, retryable=True)
