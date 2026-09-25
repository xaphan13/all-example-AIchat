"""Пример: чат с агрегатором моделей (OpenRouter и аналоги).

Пакет без обязательных внешних зависимостей на уровне импорта: `chat.py` и
`config.py` работают всегда, а `httpx_client` / `openai_client` тянут свою
библиотеку только тогда, когда выбран соответствующий backend.
"""

from .chat import (
    ChatClient,
    ChatMessage,
    ChatResult,
    ProviderError,
    Usage,
    create_client,
)
from .config import Settings

__all__ = [
    "ChatClient",
    "ChatMessage",
    "ChatResult",
    "ProviderError",
    "Settings",
    "Usage",
    "create_client",
]
