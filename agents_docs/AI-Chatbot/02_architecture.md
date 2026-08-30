# 02 — Архитектура и паттерны

## Высокоуровневая архитектура

Проект построен как **монолитное SSR-приложение** (Server-Side Rendering) на FastAPI без разделения на микросервисы. Архитектура — **слоистая** с неявным разделением ответственности:

```
┌─────────────────────────────────────────────────────┐
│                   Презентационный слой                │
│   Jinja2 Templates (HTML) + Vanilla JS + Tailwind    │
│   landing.html / login.html / signup.html / index    │
└────────────────────────┬────────────────────────────┘
                         │ HTTP (HTML pages + JSON API)
┌────────────────────────▼────────────────────────────┐
│                    Слой API (контроллеры)              │
│  app/main.py          — HTML-роуты (/, /login, /chat) │
│  app/api/v1/chat.py   — POST /api/chat                │
│  app/api/v1/users.py  — FastAPIUsers (auth/register)  │
└────────────────────────┬────────────────────────────┘
                         │ вызовы функций / Depends
┌────────────────────────▼────────────────────────────┐
│                  Слой бизнес-логики                    │
│  app/services/chat.py        — get_chat_response()    │
│  app/services/user_manager.py — UserManager            │
└──────────┬─────────────────────────────┬─────────────┘
           │                             │
           ▼                             ▼
┌─────────────────────┐     ┌──────────────────────────┐
│   Слой данных (ORM)  │     │    Внешний сервис (LLM)   │
│  app/models/users.py │     │  GitHub Models API        │
│  app/db/session.py   │     │  (AsyncOpenAI client)     │
│  app/db/base.py      │     └──────────────────────────┘
│  SQLite (aiosqlite)  │
└─────────────────────┘
```

### Характеристики

- **Тип**: Монолит, SSR + REST API в одном процессе
- **Язык**: Python 3.13 (async/await throughout)
- **Парадигма**: Объектно-ориентированная + функциональная (FastAPI dependency injection)
- **Протокол**: HTTP/1.1, синхронный запрос-ответ (без WebSocket, без SSE)
- **Состояние**: Stateless на уровне приложения (состояние — в БД и JWT-токенах)

---

## Основные паттерны проектирования

### 1. Dependency Injection (FastAPI `Depends`)

Используется повсеместно через нативный механизм FastAPI:

- `get_db()` (`app/db/session.py:11`) — внедряет async-сессию БД
- `get_user_manager()` (`app/services/user_manager.py:21`) — внедряет `UserManager` с подключённой `SQLAlchemyUserDatabase`
- `current_user` (`app/api/v1/users.py:50`) — внедряет текущего аутентифицированного пользователя (через `fastapi_users.current_user()`)

```python
# Пример: app/api/v1/chat.py:13
async def chat_endpoint(prompt: ChatRequest = Body(...), user: User = Depends(current_user)):
```

### 2. Strategy (Authentication Backends)

В `app/api/v1/users.py` реализован паттерн Strategy через `AuthenticationBackend` из FastAPI-Users:

- `jwt_auth_backend` — Bearer-токен (для API-клиентов)
- `cookie_auth_backend` — Cookie (для браузерных сессий)

Оба используют общую `JWTStrategy` (`get_jwt_strategy()`, lifetime=3600с). Роутеры `login_router` и `register_router` привязаны к cookie-backend.

### 3. Singleton (модульные синглтоны)

Следующие объекты создаются один раз на уровне модуля (при импорте):

- `settings` (`app/core/config.py:26`) — конфигурация
- `engine` и `AsyncSession` (`app/db/session.py:5-6`) — движок БД и фабрика сессий
- `client` (`app/services/chat.py:5`) — AsyncOpenAI-клиент
- `templates` (`app/core/templates.py:3`) — Jinja2Templates (но в `main.py` создаётся **отдельный** экземпляр)

### 4. Active Record / Data Mapper (SQLAlchemy 2.0)

Модель `User` (`app/models/users.py:8`) использует декларативный стиль SQLAlchemy 2.0 (`DeclarativeBase`, `Mapped`, `mapped_column`). Доступ к данным — через `SQLAlchemyUserDatabase` (адаптер FastAPI-Users), а не через кастомный Repository.

### 5. DTO (Data Transfer Object)

Pydantic-схемы выполняют роль DTO для валидации и сериализации:

- `ChatRequest` (`app/schemas/chat.py:4`) — входной DTO для чата
- `UserRead` / `UserCreate` / `UserUpdate` (`app/schemas/users.py:6-14`) — DTO для пользовательских операций

### Паттерны, которые **отсутствуют**, но ожидаемы

- **Repository Pattern** — нет абстракции над доступом к данным (всё через FastAPI-Users)
- **Unit of Work** — нет управления транзакциями на уровне бизнес-логики
- **Service Layer** — сервисы есть, но не инкапсулируют транзакции и оркестрацию
- **Middleware Pipeline** — нет кастомных middleware (CORS, rate limiting, logging)

---

## Схема потока данных (Data Flow)

### Поток: Отправка сообщения в чат

```
Пользователь (браузер)
  │
  │  POST /api/chat
  │  Body: { "prompt": "Hello" }
  │  Cookie: fastapiusersauth=<jwt>
  │
  ▼
┌─────────────────────────────────────────────────────────────┐
│  FastAPI ASGI (uvicorn)                                       │
│  app/main.py — роутер /api → app/api/v1/chat.py:router        │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  Endpoint: chat_endpoint()                                    │
│  app/api/v1/chat.py:13                                        │
│                                                               │
│  1. Валидация тела запроса → ChatRequest (Pydantic)           │
│  2. Depends(current_user) → извлечение JWT из cookie          │
│     → декодирование → запрос User из БД                       │
│     → если не аутентифицирован → 401 Unauthorized             │
│  3. Вызов get_chat_response(prompt=prompt.prompt)             │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  Service: get_chat_response()                                 │
│  app/services/chat.py:11                                      │
│                                                               │
│  1. Конкатенация системного промпта + пользовательского ввода │
│  2. AsyncOpenAI.chat.completions.create(                      │
│       model="openai/gpt-4o",                                  │
│       messages=[{role:"user", content: message}]              │
│     )                                                         │
│  3. HTTP-запрос к https://models.github.ai/inference/         │
│     (через openai SDK, Bearer = GITHUB_TOKEN)                 │
│  4. Извлечение response.choices[0].message.content            │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  Возврат: {"response": "<AI text>"}                          │
│  → JSON-сериализация → HTTP 200 → браузер                    │
│  → JS-клиент (index.html:200) отрисовывает сообщение          │
└─────────────────────────────────────────────────────────────┘
```

### Поток: Регистрация пользователя

```
Браузер (signup.html)
  │  POST /auth/register
  │  Body: { email, password, full_name }
  ▼
FastAPIUsers register_router (app/api/v1/users.py:48)
  │  Depends(get_user_manager) → UserManager
  │  Depends(get_async_session) → SQLAlchemyUserDatabase
  ▼
UserManager.on_after_register()  (app/services/user_manager.py:17)
  │  → print() логирование
  ▼
SQLAlchemy → INSERT INTO user (id, email, hashed_password, ...)
  │  → SQLite (aiosqlite)
  ▼
Response: UserRead JSON → браузер → redirect to /login
```

### Поток: Вход в систему (Cookie-auth)

```
Браузер (login.html)
  │  POST /auth/login  (form-urlencoded: username=email, password)
  ▼
FastAPIUsers login_router (cookie_auth_backend)
  │  → аутентификация (verify password)
  │  → генерация JWT (JWTStrategy, secret=SECRET, lifetime=3600s)
  │  → установка cookie "fastapiusersauth" (HttpOnly, max_age=3600)
  ▼
HTTP 200 + Set-Cookie → браузер → redirect to /chat
```

---

## Управление состоянием

### Состояние приложения

| Тип | Где хранится | Механизм |
|---|---|---|
| **Пользовательские данные** | SQLite (`./sqlite.db`) | SQLAlchemy ORM, таблица `user` |
| **Аутентификация** | JWT в Cookie | `fastapiusersauth` cookie, lifetime=3600с |
| **Сессия чата** | **Не сохраняется** | Каждый запрос `/api/chat` — независимый, без контекста предыдущих сообщений |
| **Конфигурация** | `.env` + переменные окружения | `pydantic-settings` → `settings` singleton |

### Кэширование

**Отсутствует.** Нет кэширования на любом уровне:
- Нет Redis / Memcached
- Нет HTTP-кэширования (Cache-Control, ETag)
- Нет кэширования ответов LLM
- Нет кэширования шаблонов (Jinja2 по умолчанию не кэширует при `--reload`)

### Управление конфигурацией

Конфигурация централизована в `app/core/config.py` через `pydantic-settings`:

```python
class Setting(BaseSettings):
    DATABASE_URL: str = "sqlite+aiosqlite:///./sqlite.db"
    GITHUB_TOKEN: str = ""                          # обязательно для работы чата
    SECRET: str = "your-secret-key-change-this..."  # для JWT (опасный дефолт)
    DEBUG: bool = False
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True)
```

- Чтение из `.env` и переменных окружения (case-sensitive)
- Нет валидации обязательности `GITHUB_TOKEN` (пустая строка — допустимое значение)
- Нет разделения на dev/staging/prod профили
- Модель LLM (`openai/gpt-4o`) и `base_url` захардкожены в `app/services/chat.py:7,20`
