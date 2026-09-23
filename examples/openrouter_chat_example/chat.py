"""Единый интерфейс чата с моделью.

Любой провайдер (агрегатор вроде OpenRouter или OpenAI-совместимый сервис)
описывается одним контрактом. Остальной код приложения работает только
с этим контрактом и не знает, какая библиотека внутри — httpx, официальный
SDK агрегатора или что-то ещё.

Перенос в другой проект: достаточно скопировать этот файл (и `config.py`
как пример чтения настроек) и подставить свою реализацию в `create_client(...)`.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass, field


@dataclass(slots=True)
class ChatMessage:
    """Одно сообщение диалога в формате, общем для всех OpenAI-совместимых API."""

    role: str  # "system" | "user" | "assistant"
    content: str

    def as_dict(self) -> dict[str, str]:
        return {"role": self.role, "content": self.content}


@dataclass(slots=True)
class Usage:
    """Расход токенов по одному ответу модели."""

    prompt_tokens: int = 0
    completion_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


@dataclass(slots=True)
class ChatResult:
    """Ответ модели целиком (режим без стриминга)."""

    content: str
    model: str
    usage: Usage = field(default_factory=Usage)
    provider: str | None = None  # какой провайдер выбрал агрегатор, если он это сообщил
    finish_reason: str | None = None

    @property
    def cost_usd(self) -> float | None:
        """Стоимость ответа, если для модели известны цены."""
        return None  # переопределяется в конкретной реализации, если цены заданы


class ChatClient(ABC):
    """Контракт клиента чата.

    Реализации обязаны:
      * принимать историю сообщений и не мутировать переданный список;
      * выбрасывать `ProviderError` при отказе провайдера, не глотая ошибку;
      * в стриминге отдавать только текст, а метаданные (usage, провайдер)
        отдавать через `stream_with_usage`.
    """

    @abstractmethod
    async def chat(
        self,
        messages: list[ChatMessage],
        *,
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> ChatResult:
        """Один запрос — один полный ответ."""

    @abstractmethod
    async def stream(
        self,
        messages: list[ChatMessage],
        *,
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> AsyncIterator[str]:
        """Один запрос — поток текстовых фрагментов по мере генерации."""

    async def stream_with_usage(
        self,
        messages: list[ChatMessage],
        *,
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> AsyncIterator[str | Usage]:
        """Поток текста, а последним элементом — `Usage`.

        Базовая реализация не умеет достать usage из потока и просто не отдаёт его.
        Реализации, которые могут, переопределяют метод.
        """
        async for chunk in self.stream(
            messages, model=model, temperature=temperature, max_tokens=max_tokens
        ):
            yield chunk

    @abstractmethod
    async def aclose(self) -> None:
        """Закрыть соединения. Клиент создаётся один раз на процесс."""


class ProviderError(RuntimeError):
    """Отказ провайдера, который не удалось пережить повторами и fallback-моделями.

    Атрибуты:
        status_code: HTTP-код, если он был (None при ошибке сети).
        model: модель, на которой всё сломалось.
        retryable: имеет ли смысл повторить запрос позже.
    """

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        model: str | None = None,
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.model = model
        self.retryable = retryable


def create_client(backend: str, *, api_key: str, base_url: str, **kwargs: object) -> ChatClient:
    """Фабрика клиентов: выбрать реализацию по имени.

    Точка расширения — здесь. Чтобы добавить нового провайдера, достаточно
    дописать ветку и не трогать остальное приложение. Импорты ленивые, чтобы
    проект не тянул одновременно обе библиотеки, если нужна только одна.

    Пример:
        client = create_client(
            "httpx",                       # или "openai"
            api_key=settings.api_key,
            base_url=settings.base_url,
            app_url=settings.app_url,      # заголовок HTTP-Referer
            app_title=settings.app_title,  # заголовок X-Title
        )
    """
    if backend == "httpx":
        from .httpx_client import HttpxChatClient

        return HttpxChatClient(api_key=api_key, base_url=base_url, **kwargs)

    if backend == "openai":
        from .openai_client import OpenAISDKChatClient

        return OpenAISDKChatClient(api_key=api_key, base_url=base_url, **kwargs)

    raise ValueError(
        f"Неизвестная реализация клиента: {backend!r}. "
        f"Доступны: 'httpx', 'openai'."
    )
