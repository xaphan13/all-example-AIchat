"""Реализация на httpx: прямой разговор с OpenAI-совместимым входом агрегатора.

Здесь ничего не скрыто: видно тело запроса, заголовки, разбор SSE и работу
с ошибками. Если проект не должен тянуть SDK — берётся эта реализация.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from typing import Any

import httpx

from .chat import ChatClient, ChatMessage, ChatResult, ProviderError, Usage

logger = logging.getLogger(__name__)

# Коды, при которых имеет смысл повторить запрос: перегрузка, лимиты, сбои на стороне сервиса.
RETRYABLE_STATUS_CODES = frozenset({408, 409, 425, 429, 500, 502, 503, 504})


class HttpxChatClient(ChatClient):
    """Клиент агрегатора на httpx.AsyncClient.

    Клиент создаётся один раз на процесс: `AsyncClient` переиспользует соединения,
    а создание его на каждый запрос убивает пул и TLS-сессии.
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
        retry_backoff_seconds: float = 0.5,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._max_retries = max(0, max_retries)
        self._retry_backoff = retry_backoff_seconds
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            timeout=httpx.Timeout(
                timeout_seconds,      # на весь запрос
                connect=5.0,          # на установку соединения
                read=timeout_seconds,  # на паузу между чанками стрима
            ),
            headers=self._headers(app_url, app_title),
        )

    @staticmethod
    def _headers(app_url: str, app_title: str) -> dict[str, str]:
        """Заголовки запроса.

        `HTTP-Referer` и `X-Title` у OpenRouter необязательны, но именно по ним
        приложение атрибутируется в статистике и рейтингах. Другие агрегаторы
        используют свои имена — при переносе меняется эта функция.
        """
        return {
            "Content-Type": "application/json",
            "HTTP-Referer": app_url,
            "X-Title": app_title,
        }

    async def _request_with_retries(self, payload: dict[str, Any]) -> httpx.Response:
        """POST с повторами на временные отказы и учётом `Retry-After`."""
        last_error: ProviderError | None = None

        for attempt in range(1, self._max_retries + 2):
            try:
                response = await self._client.post("/chat/completions", json=payload)
            except httpx.TimeoutException as error:
                last_error = ProviderError(
                    f"Таймаут запроса к агрегатору: {error}",
                    model=payload.get("model"),
                    retryable=True,
                )
            except httpx.HTTPError as error:
                last_error = ProviderError(
                    f"Сетевая ошибка при запросе к агрегатору: {error}",
                    model=payload.get("model"),
                    retryable=True,
                )
            else:
                if response.status_code < 400:
                    return response

                body = response.text[:500]
                last_error = ProviderError(
                    f"Агрегатор вернул {response.status_code}: {body}",
                    status_code=response.status_code,
                    model=payload.get("model"),
                    retryable=response.status_code in RETRYABLE_STATUS_CODES,
                )
                if not last_error.retryable:
                    raise last_error

                retry_after = self._retry_after_seconds(response)
                if attempt <= self._max_retries and retry_after is not None:
                    await asyncio.sleep(retry_after)
                    continue

            # Сюда попадаем после сетевой ошибки или таймаута.
            if attempt > self._max_retries:
                raise last_error

            delay = self._retry_backoff * (2 ** (attempt - 1))
            logger.warning(
                "Повтор запроса к агрегатору через %.1f с (попытка %d из %d): %s",
                delay, attempt, self._max_retries + 1, last_error,
            )
            await asyncio.sleep(delay)

        raise last_error or ProviderError("Запрос не удался", model=payload.get("model"))

    @staticmethod
    def _retry_after_seconds(response: httpx.Response) -> float | None:
        """Сколько агрегатор просил подождать (заголовок `Retry-After`), если он есть."""
        raw = response.headers.get("retry-after")
        if not raw:
            return None
        try:
            return max(0.0, float(raw))
        except ValueError:
            return None

    def _payload(
        self,
        messages: list[ChatMessage],
        *,
        model: str,
        temperature: float,
        max_tokens: int,
        stream: bool,
    ) -> dict[str, Any]:
        return {
            "model": model,
            "messages": [m.as_dict() for m in messages],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": stream,
        }

    async def chat(
        self,
        messages: list[ChatMessage],
        *,
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> ChatResult:
        payload = self._payload(
            messages, model=model, temperature=temperature,
            max_tokens=max_tokens, stream=False,
        )
        response = await self._request_with_retries(payload)
        data = response.json()

        if not data.get("choices"):
            raise ProviderError(f"Ответ без choices: {str(data)[:500]}", model=model)

        choice = data["choices"][0]
        raw_usage = data.get("usage") or {}

        return ChatResult(
            content=choice.get("message", {}).get("content") or "",
            model=data.get("model", model),
            usage=Usage(
                prompt_tokens=raw_usage.get("prompt_tokens", 0),
                completion_tokens=raw_usage.get("completion_tokens", 0),
            ),
            provider=data.get("provider"),
            finish_reason=choice.get("finish_reason"),
        )

    async def stream(
        self,
        messages: list[ChatMessage],
        *,
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> AsyncIterator[str]:
        """Поток текста. Метаданные не отдаются — для них есть `stream_with_usage`."""
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
        """Поток текста, последним элементом — расход токенов.

        Тонкость агрегаторов: usage приходит ровно один раз, в последнем чанке
        перед `[DONE]`, и — вопреки спецификации OpenAI — этот чанк содержит
        непустой массив `choices`. Поэтому последний чанк разбирается отдельно,
        а не отбрасывается.
        """
        payload = self._payload(
            messages, model=model, temperature=temperature,
            max_tokens=max_tokens, stream=True,
        )
        retries_left = self._max_retries
        attempt = 0

        while True:
            attempt += 1
            final_usage: Usage | None = None
            emitted_text = False

            try:
                async with self._client.stream(
                    "POST", "/chat/completions", json=payload
                ) as response:
                    if response.status_code >= 400:
                        body = (await response.aread()).decode("utf-8", "replace")[:500]
                        raise ProviderError(
                            f"Агрегатор вернул {response.status_code}: {body}",
                            status_code=response.status_code,
                            model=model,
                            retryable=response.status_code in RETRYABLE_STATUS_CODES,
                        )

                    async for line in response.aiter_lines():
                        chunk = self._parse_sse_line(line)
                        if chunk is None:
                            continue

                        if chunk.get("usage"):
                            raw = chunk["usage"]
                            final_usage = Usage(
                                prompt_tokens=raw.get("prompt_tokens", 0),
                                completion_tokens=raw.get("completion_tokens", 0),
                            )

                        for choice in chunk.get("choices") or []:
                            text = (choice.get("delta") or {}).get("content")
                            if text:
                                emitted_text = True
                                yield text

                if final_usage is not None:
                    yield final_usage
                return

            except ProviderError as error:
                # Стрим не переигрывается, если текст уже ушёл пользователю:
                # повтор дублировал бы вывод. Отсюда `emitted_text`.
                if emitted_text or not error.retryable or retries_left <= 0:
                    raise
                retries_left -= 1
                delay = self._retry_backoff * (2 ** (attempt - 1))
                logger.warning(
                    "Повтор стрима через %.1f с: %s", delay, error,
                )
                await asyncio.sleep(delay)

    @staticmethod
    def _parse_sse_line(line: str) -> dict[str, Any] | None:
        """Разобрать одну строку SSE. Возвращает None для служебных строк."""
        if not line or not line.startswith("data:"):
            return None

        payload = line[len("data:"):].strip()
        if payload == "[DONE]":
            return None

        try:
            return json.loads(payload)
        except json.JSONDecodeError:
            logger.debug("Пропущена неразбираемая строка SSE: %r", line[:200])
            return None

    async def aclose(self) -> None:
        await self._client.aclose()
