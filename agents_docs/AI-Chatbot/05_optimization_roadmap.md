# 05 — Предложения по развитию

## Приоритизация

Предложения разделены по приоритету: **P0** (критично, блокирует работу), **P1** (высокий, влияет на безопасность/надёжность), **P2** (средний, влияет на DX и масштабируемость), **P3** (низкий, улучшение качества).

---

## Архитектурные улучшения

### P0: Исправить запуск приложения — создать `app/static/` или убрать монтирование

**Проблема:** `app/main.py:20` вызывает `StaticFiles(directory="app/static")`, но директория не существует → `RuntimeError` при запуске.

**Решение:**
```python
# Вариант 1: создать директорию
mkdir app/static

# Вариант 2: условное монтирование
import os
if os.path.isdir("app/static"):
    app.mount("/static", StaticFiles(directory="app/static"), name="static")
```

### P1: Сохранение истории чата и контекста беседы

**Проблема:** Каждый запрос `/api/chat` — stateless. Контекст предыдущих сообщений теряется. LLM не "помнит" разговор.

**Решение:**

1. Создать модели `Conversation` и `Message`:

```
app/models/
├── users.py
├── conversation.py   # Conversation: id, user_id, created_at, title
└── message.py        # Message: id, conversation_id, role, content, created_at
```

2. Обновить `app/services/chat.py` для передачи истории в `messages` параметр OpenAI API
3. Добавить эндпоинты: `GET /api/conversations`, `GET /api/conversations/{id}/messages`, `POST /api/conversations/{id}/chat`
4. Создать Alembic-миграцию для новых таблиц

### P1: Streaming ответов через SSE

**Проблема:** Пользователь ждёт полной генерации LLM (2-10 секунд) без обратной связи.

**Решение:**
```python
# app/api/v1/chat.py
from fastapi.responses import StreamingResponse
from app.services.chat import stream_chat_response

@router.post("/chat")
async def chat_endpoint(prompt: ChatRequest = Body(...), user: User = Depends(current_user)):
    return StreamingResponse(
        stream_chat_response(prompt.prompt, user),
        media_type="text/event-stream"
    )
```

```python
# app/services/chat.py
async def stream_chat_response(prompt: str, user):
    stream = await client.chat.completions.create(
        model="openai/gpt-4o",
        messages=[...],
        stream=True,
    )
    async for chunk in stream:
        if chunk.choices[0].delta.content:
            yield f"data: {json.dumps({'content': chunk.choices[0].delta.content})}\n\n"
    yield "data: [DONE]\n\n"
```

### P2: Конфигурируемость LLM-параметров

**Проблема:** Модель `openai/gpt-4o`, `base_url`, системный промпт — захардкожены в `app/services/chat.py`.

**Решение:** Вынести в `app/core/config.py`:
```python
class Setting(BaseSettings):
    LLM_MODEL: str = "openai/gpt-4o"
    LLM_BASE_URL: str = "https://models.github.ai/inference/"
    LLM_SYSTEM_PROMPT: str = "You are a helpful AI assistant."
    LLM_TEMPERATURE: float = 0.7
    LLM_MAX_TOKENS: int = 1000
    LLM_TIMEOUT: int = 30
```

### P2: Миграция на PostgreSQL

**Проблема:** SQLite не масштабируется для concurrent writes.

**Решение:**
1. Добавить `asyncpg` в зависимости
2. Изменить `DATABASE_URL` на `postgresql+asyncpg://...`
3. Обновить `alembic/env.py` (убрать хак с заменой драйвера на строке 19)
4. Alembic-миграция совместима — достаточно `alembic upgrade head`

### P3: Разделение auth-конфигурации в отдельный модуль

**Проблема:** `app/api/v1/users.py` — это "божественный модуль", конфигурирующий FastAPIUsers, создающий backends, роутеры и экспортирующий `current_user`. Router `chat.py` зависит от него.

**Решение:**
```
app/core/
├── config.py
├── security.py      # JWT strategy, auth backends, current_user dependency
└── templates.py
```

---

## Оптимизация производительности

### P1: Добавить timeout на LLM-запросы

**Файл:** `app/services/chat.py:19`

```python
response = await asyncio.wait_for(
    client.chat.completions.create(model=..., messages=...),
    timeout=30
)
```

Или через параметр OpenAI клиента:
```python
client = AsyncOpenAI(api_key=..., base_url=..., timeout=30.0)
```

### P1: Обработка ошибок LLM API

**Файл:** `app/services/chat.py`

```python
from openai import APIError, APIConnectionError, RateLimitError, APITimeoutError

async def get_chat_response(prompt: str) -> str:
    try:
        response = await client.chat.completions.create(...)
        return response.choices[0].message.content.strip() if response.choices else ""
    except APITimeoutError:
        raise ChatServiceError("AI service timed out. Please try again.")
    except RateLimitError:
        raise ChatServiceError("Rate limit exceeded. Please wait a moment.")
    except APIConnectionError:
        raise ChatServiceError("Unable to connect to AI service.")
    except APIError as e:
        raise ChatServiceError(f"AI service error: {e.message}")
```

### P2: Заменить Tailwind CDN на сборку

**Проблема:** `cdn.tailwindcss.com` — runtime-компиляция в браузере, ~300KB JS.

**Решение:**
```bash
npm init -y
npm install -D tailwindcss
npx tailwindcss init
```
Собрать минифицированный CSS и разместить в `app/static/css/style.css`.

### P2: Кэширование HTML-шаблонов

Убрать `--reload` в production, Jinja2 автоматически кэширует скомпилированные шаблоны.

### P3: Connection pool для OpenAI клиента

```python
import httpx
http_client = httpx.AsyncClient(max_connections=100, max_keepalive_connections=20)
client = AsyncOpenAI(api_key=..., base_url=..., http_client=http_client)
```

---

## Рефакторинг — первоочередные файлы

| Приоритет | Файл | Обоснование | Действие |
|-----------|------|-------------|----------|
| **P0** | `app/main.py` | StaticFiles crash; HTML-роуты смешаны с setup; нет lifespan | Условное монтирование static; вынести HTML-роуты в `app/api/pages.py`; добавить `lifespan` для cleanup |
| **P0** | `app/services/chat.py` | Захардкожены модель/промпт; нет error handling; нет timeout | Параметризовать через config; добавить try/except; добавить timeout |
| **P1** | `app/core/config.py` | Опасный дефолт SECRET; нет валидации GITHUB_TOKEN; нет LLM-параметров | Валидатор на пустой GITHUB_TOKEN; убрать дефолт SECRET; добавить LLM-настройки |
| **P1** | `app/api/v1/users.py` | Экспортирует `current_user` — нарушение инкапсуляции; смешивает конфигурацию и роутеры | Вынести `current_user` и auth-конфиг в `app/core/security.py` |
| **P1** | `app/services/user_manager.py` | `print()` вместо logging; `SECRET` дублируется | Заменить на `logging`; использовать `settings.SECRET` напрямую |
| **P1** | `app/templates/index.html` | XSS через `innerHTML`; нет base template; нет streaming | Использовать `textContent` или санитизацию; выделить `base.html` |
| **P2** | `app/templates/*.html` | Дублирование CSS/HTML между 4 шаблонами | Создать `base.html` с блоками `{% block content %}` |
| **P2** | `app/db/session.py` | `echo=settings.DEBUG` — утечка SQL | Заменить на SQLAlchemy `logging` с уровнем WARNING |
| **P2** | `pyproject.toml` | `ruff`/`black` в основных зависимостях | Перенести в `[dependency-groups] dev` |
| **P2** | `app/core/templates.py` | Неиспользуемый модуль | Удалить или использовать везде вместо дубликата в `main.py` |

---

## Рекомендации по улучшению DX (Developer Experience)

### P1: Создать `.env.example`

```env
# Required
GITHUB_TOKEN=your_github_personal_access_token
SECRET=generate-a-random-secret-key-here

# Database
DATABASE_URL=sqlite+aiosqlite:///./sqlite.db

# Optional
DEBUG=False
LLM_MODEL=openai/gpt-4o
LLM_BASE_URL=https://models.github.ai/inference/
```

### P1: Добавить тесты

```
tests/
├── conftest.py              # Фикстуры: test client, test DB, mock OpenAI
├── test_auth.py             # Регистрация, логин, логаут
├── test_chat.py             # Чат-эндпоинт (с mock LLM)
├── test_pages.py            # HTML-страницы (200, redirect при no-auth)
└── test_models.py           # Модель User
```

Минимальный набор:
```python
# tests/conftest.py
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app

@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
```

Добавить в `pyproject.toml`:
```toml
[dependency-groups]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "httpx>=0.27",
    "respx>=0.21",  # mock для httpx/openai
]
```

### P2: CI/CD Pipeline (GitHub Actions)

```yaml
# .github/workflows/ci.yml
name: CI
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.13"
      - run: pip install uv && uv sync
      - run: uv run ruff check .
      - run: uv run pytest --cov=app
```

### P2: Dockerfile для локального запуска и деплоя

```dockerfile
FROM python:3.13-slim
WORKDIR /app
RUN pip install uv
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen
COPY . .
RUN uv run alembic upgrade head
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### P2: Makefile / Taskfile для типовых команд

```makefile
dev:
	uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

migrate:
	uv run alembic upgrade head

migrate-new:
	uv run alembic revision --autogenerate -m "$(msg)"

test:
	uv run pytest -v

lint:
	uv run ruff check .
	uv run black --check .

format:
	uv run ruff format .
	uv run black .
```

### P3: Структурное логирование

```python
# app/core/logging.py
import logging
import sys

def setup_logging(debug: bool = False):
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        stream=sys.stdout,
    )
    # Подавить SQL-логи SQLAlchemy
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
```

Вызывать в `lifespan` handler'е приложения.

### P3: Согласовать версию Python

Обновить `README.md` — указать Python 3.13+ (соответствие `pyproject.toml` и `.python-version`).

---

## Итоговая дорожная карта

| Этап | Задачи | Ожидаемый эффект |
|------|--------|------------------|
| **Спринт 1** (P0) | Создать `app/static/`; исправить `config.py` (SECRET, GITHUB_TOKEN); добавить error handling + timeout в `chat.py` | Приложение запускается и не падает на ошибках LLM |
| **Спринт 2** (P1) | `.env.example`; базовые тесты; вынос `current_user` в `security.py`; логирование вместо `print`; исправить XSS в `index.html` | Безопасность + тестируемость |
| **Спринт 3** (P2) | История чата (Conversation/Message модели); SSE streaming; CI/CD; Dockerfile; base.html для шаблонов | Product-grade функциональность + DX |
| **Спринт 4** (P3) | PostgreSQL миграция; Tailwind build; структурное логирование; rate limiting | Масштабируемость + production-readiness |
