"""Реализация на httpx: прямой разговор с OpenAI-совместимым входом агрегатора.

Здесь ничего не скрыто: видно тело запроса, заголовки и разбор SSE. Если проект
не должен тянуть SDK — берётся эта реализация.

Клиент ничего не повторяет: при отказе он выбрасывает `ProviderError`, а решать,
менять ли модель, — дело вызывающего кода.
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from typing import Any

import httpx

from .chat import ChatClient, ChatMessage, ChatResult, ProviderError, Usage

logger = logging.getLogger(__name__)

# Коды, означающие временный отказ: перегрузка, лимиты, сбои на стороне сервиса.
# На них имеет смысл попробовать другую модель, на 400/401 — нет.
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
    ) -> None:
        self._api_key = api_key
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            timeout=httpx.Timeout(
                timeout_seconds,       # на весь запрос
                connect=5.0,           # на установку соединения
                read=timeout_seconds,  # на паузу между чанками стрима
            ),
            headers={
                "Content-Type": "application/json",
                # У OpenRouter эти заголовки необязательны, но именно по ним
                # приложение атрибутируется в статистике. У другого агрегатора
                # имена будут другие — меняется только этот словарь.
                "HTTP-Referer": app_url,
                "X-Title": app_title,
            },
        )

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
            "messages": [m.model_dump() for m in messages],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": stream,
        }

    @staticmethod
    def _raise_for_status(response: httpx.Response) -> None:
        """Превратить HTTP-ошибку в `ProviderError` с признаком временности."""
        if response.status_code < 400:
            return
        raise ProviderError(
            f"Агрегатор вернул {response.status_code}: {response.text[:500]}",
            status_code=response.status_code,
            retryable=response.status_code in RETRYABLE_STATUS_CODES,
        )

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

        try:
            response = await self._client.post("/chat/completions", json=payload)
        except httpx.HTTPError as error:
            raise ProviderError(f"Сетевая ошибка: {error}", model=model) from error

        self._raise_for_status(response)
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
        """Поток текста по мере генерации.

        Разбор SSE сделан руками: строка `data: {...}` на каждый чанк, служебные
        строки и `[DONE]` пропускаются. В стриме важен только `delta.content`.
        """
        payload = self._payload(
            messages, model=model, temperature=temperature,
            max_tokens=max_tokens, stream=True,
        )

        try:
            async with self._client.stream(
                "POST", "/chat/completions", json=payload
            ) as response:
                if response.status_code >= 400:
                    body = (await response.aread()).decode("utf-8", "replace")
                    raise ProviderError(
                        f"Агрегатор вернул {response.status_code}: {body[:500]}",
                        status_code=response.status_code,
                        model=model,
                        retryable=response.status_code in RETRYABLE_STATUS_CODES,
                    )

                async for line in response.aiter_lines():
                    chunk = self._parse_sse_line(line)
                    if chunk is None:
                        continue
                    for choice in chunk.get("choices") or []:
                        text = (choice.get("delta") or {}).get("content")
                        if text:
                            yield text
        except httpx.HTTPError as error:
            raise ProviderError(f"Сетевая ошибка: {error}", model=model) from error

    @staticmethod
    def _parse_sse_line(line: str) -> dict[str, Any] | None:
        """Разобрать одну строку SSE. Возвращает None для служебных строк."""
        if not line.startswith("data:"):
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
