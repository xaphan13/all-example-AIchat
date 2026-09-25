"""Единый интерфейс чата с моделью.

Любой провайдер (агрегатор вроде OpenRouter или OpenAI-совместимый сервис)
описывается одним контрактом. Остальной код приложения работает только
с этим контрактом и не знает, какая библиотека внутри — httpx, официальный
SDK или что-то ещё.

Перенос в другой проект: достаточно скопировать этот файл и подставить свою
реализацию в `create_client(...)`.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass, field

from pydantic import BaseModel, Field

# Роли, которые понимает формат Chat Completions.
Role = str


class ChatMessage(BaseModel):
    """Одно сообщение диалога.

    Модель pydantic, а не датакласс, потому что это данные из внешнего мира:
    роль приходит из пользовательского ввода и её стоит проверить до запроса,
    а не получить 400 от провайдера.
    """

    role: Role = Field(description='"system", "user" или "assistant"')
    content: str


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


class ChatClient(ABC):
    """Контракт клиента чата.

    Всего два метода и закрытие. Реализации обязаны выбрасывать `ProviderError`
    при отказе провайдера, а не глотать ошибку и не возвращать пустой ответ.
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

    @abstractmethod
    async def aclose(self) -> None:
        """Закрыть соединения. Клиент создаётся один раз на процесс."""


class ProviderError(RuntimeError):
    """Отказ провайдера, который не удалось пережить fallback-моделями.

    Атрибуты:
        status_code: HTTP-код, если он был (None при ошибке сети).
        model: модель, на которой всё сломалось.
        retryable: имеет ли смысл попробовать другую модель (временный сбой,
            а не ошибка самого запроса).
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
            "httpx",                  # или "openai"
            api_key=settings.api_key,
            base_url=settings.base_url,
            app_url=settings.app_url,
            app_title=settings.app_title,
        )
    """
    if backend == "httpx":
        from .httpx_client import HttpxChatClient

        return HttpxChatClient(api_key=api_key, base_url=base_url, **kwargs)

    if backend == "openai":
        from .openai_client import OpenAISDKChatClient

        return OpenAISDKChatClient(api_key=api_key, base_url=base_url, **kwargs)

    raise ValueError(
        f"Неизвестная реализация клиента: {backend!r}. Доступны: 'httpx', 'openai'."
    )
