# 01 — Карта проекта

## Назначение проекта

**AI Chatbot Assistant** — веб-приложение на базе FastAPI, предоставляющее пользовательский интерфейс чата с AI-моделью. Бэкенд использует GitHub Models API (OpenAI-совместимый эндпоинт) для инференса LLM, FastAPI-Users для управления пользователями и JWT/Cookie-аутентификации, а также SQLAlchemy (async) с SQLite в качестве хранилища. Фронтенд реализован на серверных Jinja2-шаблонах с Tailwind CSS (CDN) и ванильным JavaScript.

Проект представляет собой **монолитное SSR-приложение** (Server-Side Rendering) без разделения на отдельные микросервисы. Вся логика — аутентификация, чат, отдача HTML-страниц — находится в единственном FastAPI-приложении.

---

## Дерево директорий и ключевых файлов

```
AI-Chatbot/
├── pyproject.toml                  # Конфигурация проекта (uv/pip): зависимости, ruff, black
├── .python-version                 # Версия Python для uv/pyenv: 3.13
├── .gitignore                      # Исключения Git (__pycache__, .env, sqlite.db, .venv)
├── alembic.ini                     # Конфигурация Alembic: путь к миграциям, логирование
├── README.md                       # Пользовательская документация (установка, запуск, API)
├── alembic/                        # Директория миграций Alembic
│   ├── env.py                      # Конфигурация окружения миграций: подставляет DATABASE_URL из settings
│   ├── script.py.mako              # Шаблон генерации файлов миграций
│   └── versions/
│       └── 5770fda647a5_create_tables.py  # Единственная миграция: создание таблицы user
└── app/                            # Основной пакет приложения
    ├── __init__.py                 # Пустой (маркер пакета)
    ├── main.py                     # Точка входа: создание FastAPI-приложения, роутинг HTML-страниц, монтирование роутеров
    ├── api/                        # Слой API (контроллеры)
    │   ├── __init__.py             # Пустой
    │   └── v1/                     # Версия API v1
    │       ├── __init__.py         # Пустой
    │       ├── chat.py             # POST /api/chat — эндпоинт чата с AI, требует аутентификации
    │       └── users.py            # Конфигурация FastAPIUsers: JWT + Cookie backends, роутеры auth/register/users
    ├── core/                       # Инфраструктурный слой (конфигурация, утилиты)
    │   ├── __init__.py             # Пустой
    │   ├── config.py               # Pydantic Settings: DATABASE_URL, GITHUB_TOKEN, SECRET, DEBUG
    │   └── templates.py            # Дублирующий экземпляр Jinja2Templates (не используется в main.py)
    ├── db/                         # Слой работы с БД
    │   ├── __init__.py             # Пустой
    │   ├── base.py                 # SQLAlchemy DeclarativeBase — корень для всех ORM-моделей
    │   └── session.py              # Async-движок, async_sessionmaker, dependency get_db()
    ├── models/                     # ORM-модели SQLAlchemy
    │   ├── __init__.py             # Пустой
    │   └── users.py                # Модель User: наследует SQLAlchemyBaseUserTableUUID + поле full_name
    ├── schemas/                    # Pydantic-схемы (DTO)
    │   ├── __init__.py             # Пустой
    │   ├── chat.py                 # ChatRequest: { prompt: str }
    │   └── users.py                # UserRead, UserCreate, UserUpdate — схемы для FastAPI-Users
    ├── services/                   # Бизнес-логика
    │   ├── __init__.py             # Пустой
    │   ├── chat.py                 # AsyncOpenAI-клиент → GitHub Models; функция get_chat_response()
    │   └── user_manager.py         # UserManager (fastapi-users), dependency get_user_manager()
    └── templates/                  # Jinja2 HTML-шаблоны (SSR-фронтенд)
        ├── landing.html            # Лендинг-страница (маркетинговый Hero + Features)
        ├── login.html              # Форма входа: POST /auth/login (form-urlencoded)
        ├── signup.html             # Форма регистрации: POST /auth/register (JSON)
        └── index.html              # Чат-интерфейс: JS-клиент, POST /api/chat, typing indicator
```

### Отсутствующие, но заявленные элементы

| Элемент | Где заявлено | Фактический статус |
|---|---|---|
| `app/static/` | `app/main.py:20` — `StaticFiles(directory="app/static")` | **Директория не существует** — приложение упадёт при запуске |
| `tests/` | `README.md:161,183-195` | **Не существует** — тестов нет |
| `.env.example` | `README.md:59` | **Не существует** |
| `requirements.txt` | `README.md:55` | **Не существует** (зависимости только в `pyproject.toml`) |

---

## Внешние зависимости и их роль

### Python-пакеты (из `pyproject.toml`)

| Пакет | Версия | Роль в проекте |
|---|---|---|
| `fastapi[standard]` | `>=0.116.1` | Веб-фреймворк: роутинг, middleware, валидация, SSR |
| `fastapi-users[sqlalchemy]` | `>=14.0.1` | Полный цикл управления пользователями: регистрация, логин, JWT/Cookie auth, ORM-адаптер |
| `openai` | `>=1.98.0` | AsyncOpenAI-клиент для запросов к GitHub Models API (OpenAI-совместимый протокол) |
| `aiosqlite` | `>=0.21.0` | Async-драйвер для SQLite (используется SQLAlchemy async engine) |
| `alembic` | `>=1.16.4` | Миграции схемы БД |
| `pydantic-settings` | `>=2.10.1` | Управление конфигурацией через `.env` и переменные окружения |
| `ruff` | `>=0.14.10` | Линтер/форматтер (должен быть dev-зависимостью, но указан в основных) |
| `black` | `>=25.0.0` | Форматтер кода (должен быть dev-зависимостью, но указан в основных) |

### Внешние сервисы

| Сервис | Endpoint | Роль |
|---|---|---|
| **GitHub Models API** | `https://models.github.ai/inference/` | LLM-инференс (модель `openai/gpt-4o`). Аутентификация через GitHub Personal Access Token (`models:read`). Вызывается через `openai` SDK с подменой `base_url`. |
| **SQLite** | Локальный файл `./sqlite.db` | Хранилище пользователей (таблица `user`). Async-доступ через `aiosqlite`. |

### CDN-зависимости фронтенда (в HTML-шаблонах)

| Ресурс | URL | Роль |
|---|---|---|
| Tailwind CSS | `https://cdn.tailwindcss.com` | CSS-фреймворк (runtime-компиляция в браузере) |
| Lucide Icons | `https://unpkg.com/lucide@latest` | SVG-иконки |
