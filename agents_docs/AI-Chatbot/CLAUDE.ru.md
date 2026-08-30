# CLAUDE.md — Руководство для Claude Code

> Инструкции для Claude Code (и других AI-агентов по написанию кода). Если вы AI-агент — прочитайте этот файл первым, затем прочитайте директорию `docs/` — это единый источник истины о проекте. Универсальная версия без привязки к харнесу — в `AGENTS.md`.

## Обзор проекта

**AI Chatbot Assistant** — веб-приложение — AI-чат-бот с полным стеком.

- **Бэкенд**: FastAPI (async), FastAPI-Users (JWT + Cookie аутентификация), SQLAlchemy 2.0 (async), SQLite через `aiosqlite`, миграции Alembic.
- **AI-инференс**: GitHub Models API (`https://models.github.ai/inference/`), доступ через `openai` SDK (`AsyncOpenAI`), модель: `openai/gpt-4o`.
- **Фронтенд**: серверный рендеринг на Jinja2-шаблонах + Tailwind CSS (CDN) + ванильный JavaScript.
- **Python**: 3.13. Менеджер пакетов: `uv`.
- **Архитектура**: монолитное слоистое SSR-приложение. Тестов и CI/CD пока нет.

## Быстрый старт (для AI-агентов)

**Не нужно обходить весь проект.** Сначала прочитайте директорию `docs/` — в ней актуальная архитектурная карта:

| Файл | Назначение |
|------|------------|
| `docs/01_project_structure.md` | Карта проекта: дерево директорий, ответственность файлов, внешние зависимости |
| `docs/02_architecture.md` | Архитектура, паттерны проектирования, поток данных, управление состоянием/конфигурацией |
| `docs/03_execution_flow.md` | Жизненный цикл приложения, бизнес-процессы, роутинг, обработка ошибок |
| `docs/04_code_quality.md` | Оценка качества, известные запахи кода, проблемы безопасности, узкие места |
| `docs/05_optimization_roadmap.md` | Дорожная карта: улучшения P0–P3, план рефакторинга, рекомендации по DX |

## Структура проекта

```
├── app/
│   ├── main.py              # Точка входа: FastAPI-приложение, HTML-роуты, подключение роутеров
│   ├── api/v1/              # Роутеры API: chat.py (POST /api/chat), users.py (конфигурация FastAPIUsers)
│   ├── core/                # config.py (Pydantic Settings), templates.py (неиспользуемый дубликат)
│   ├── db/                  # base.py (DeclarativeBase), session.py (async engine + get_db)
│   ├── models/              # users.py — ORM-модель User
│   ├── schemas/             # Pydantic DTO: chat.py (ChatRequest), users.py (UserRead/UserCreate/UserUpdate)
│   ├── services/            # chat.py (LLM-клиент), user_manager.py (UserManager из FastAPI-Users)
│   └── templates/           # landing.html, login.html, signup.html, index.html (UI чата)
├── alembic/                 # Миграции (versions/5770fda647a5_create_tables.py)
├── docs/                    # ← ЕДИНЫЙ ИСТОЧНИК ИСТИНЫ (см. таблицу выше)
├── pyproject.toml           # Зависимости, конфигурация ruff/black
└── alembic.ini              # Конфигурация Alembic
```

## Команды сборки / запуска / тестирования

```bash
# Установка зависимостей
uv sync

# Запуск миграций
uv run alembic upgrade head

# Запуск приложения (dev)
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Создание новой миграции
uv run alembic revision --autogenerate -m "<message>"

# Линт и форматирование
uv run ruff check .
uv run ruff format .
uv run black .

# Тесты
# ВНИМАНИЕ: тестового набора пока нет — см. docs/05_optimization_roadmap.md
```

## Стиль кода и конвенции

- Python 3.13, async/await везде (без синхронного БД/IO в обработке запросов).
- Декларативный стиль SQLAlchemy 2.0: `Mapped[...]`, `mapped_column`, `DeclarativeBase`.
- Pydantic v2-схемы как DTO (`pydantic-settings` для конфигурации).
- Ruff: `line-length = 100`; Black: `line-length = 120` (они конфликтуют — предпочитайте Ruff format).
- Docstring'и на английском, где присутствуют.
- Следуйте существующей слоистой структуре: `api/v1/` (роутеры) → `services/` (бизнес-логика) → `models/` + `db/` (данные).

## Критические замечания и грабли

- **Директория `app/static/` не существует** — `app/main.py:20` монтирует `StaticFiles` на неё, что вызовет `RuntimeError` при запуске. Перед запуском создайте директорию или защитите монтирование.
- **`GITHUB_TOKEN` обязателен** для работы чата; читается из `.env` / переменных окружения через `app/core/config.py`.
- **`SECRET` имеет небезопасный дефолт** в `app/core/config.py:16` — для реальных деплоев всегда задавайте через `.env`.
- **Чат stateless**: каждый вызов `POST /api/chat` независим; сохранения сообщений/бесед нет.
- **LLM-вызовы без таймаута и без обработки ошибок** в `app/services/chat.py` — ошибки всплывают как HTTP 500.
- **Известные проблемы безопасности** (из `docs/04_code_quality.md`): prompt injection в `app/services/chat.py`, XSS через `innerHTML` в `app/templates/index.html:225`.
- **Jinja2Templates создаётся дважды**: `app/main.py:19` и `app/core/templates.py` (последний не используется).
- **Alembic**: `alembic/env.py` заменяет `sqlite+aiosqlite` → `sqlite` перед запуском миграций (строка 19).
- **`pyproject.toml` требует Python >=3.13** — не снижайте синтаксис под старые версии.

## При внесении изменений

1. Сначала прочитайте соответствующие файлы в `docs/` (особенно `docs/02_architecture.md` и `docs/03_execution_flow.md`).
2. Вносите минимальные изменения; сохраняйте существующую слоистую структуру.
3. Если меняете интерфейс (сигнатуру функции, путь роутера, схему) — обновите все места вызова.
4. При добавлении/удалении полей БД сгенерируйте Alembic-миграцию.
5. Обновите соответствующий файл в `docs/`, если меняется архитектура или поток данных.
