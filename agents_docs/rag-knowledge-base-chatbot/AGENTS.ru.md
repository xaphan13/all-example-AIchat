# AGENTS.md

Универсальный файл-руководство для AI-агентов программирования — работает с любым харнессом (Claude Code, Cursor, Codex, GitHub Copilot, Aider, Gemini CLI и др.). Файл `CLAUDE.md` содержит заметки, специфичные для Claude Code; этот файл применим везде.

> English version: [AGENTS.md](AGENTS.md)

## Обзор проекта

**Auto Reply Chatbot | Support AI Assistant** — корпоративный RAG-чат-бот (Retrieval-Augmented Generation), который отвечает на вопросы поддержки из базы знаний (документы, политики, FAQ, прайсы, тикеты WHMCS) с помощью гибридного поиска (BM25 + векторный поиск) и многофазного LLM-пайплайна.

- **API**: FastAPI (Python 3.11+), точка входа `app/main.py`
- **Frontend**: админ-панель React 19 + Vite 7 (`frontend/`)
- **Инфраструктура**: PostgreSQL, Redis, OpenSearch (BM25), Qdrant (векторный поиск), MinIO (S3), Celery worker
- **Пайплайн**: Normalizer (LLM) → машина состояний Orchestrator (RETRIEVE → ASSESS → DECIDE → GENERATE → VERIFY) → Reviewer gate → финальный ответ

## Сначала читай документацию — не обходи весь репозиторий

Папка `docs/` — авторитетный источник информации об устройстве проекта. **Сначала прочитай соответствующую документацию, а уже потом лезь в код — не обходи весь репозиторий.**

| Документ | Что описывает |
|---|---|
| `docs/01_project_structure.md` | Полное дерево каталогов, назначение каждого модуля, внешние зависимости |
| `docs/02_architecture.md` | Архитектура и паттерны, поток данных RAG, поток ingestion, кэширование и конфигурация |
| `docs/03_execution_flow.md` | Жизненный цикл приложения, бизнес-процессы, цепочка middleware, маршруты, обработка ошибок, graceful degradation |
| `docs/04_code_quality.md` | Оценка качества кода, технический долг, замечания по безопасности и надёжности |
| `docs/05_optimization_roadmap.md` | Предложения по рефакторингу и оптимизации производительности (приоритизированные) |

С чего начать:

- Новый в проекте → `docs/01_project_structure.md`, затем `docs/02_architecture.md`
- Работаешь над конкретным эндпоинтом/процессом → `docs/03_execution_flow.md`
- Рефакторинг → `docs/05_optimization_roadmap.md` (готовые предложения) + `docs/04_code_quality.md`
- Отладка → `docs/03_execution_flow.md` (обработка ошибок, логирование, debug payload)

## Ключевые точки входа

| Путь | Назначение |
|---|---|
| `app/main.py` | Фабрика FastAPI, цепочка middleware, lifespan startup |
| `app/services/answer_service.py` | Точка входа в RAG — `AnswerService.generate()` |
| `app/services/orchestrator.py` | Машина состояний пайплайна |
| `app/api/routes/` | По одному файлу на группу маршрутов (conversations, reply, documents, tickets, admin, auth, ...) |
| `app/search/` | Провайдеры OpenSearch / Qdrant / embeddings / reranker |
| `worker/tasks.py` | Асинхронные задачи ingestion (Celery) |
| `alembic/versions/` | Миграции БД (001–011) |
| `tests/` | pytest-набор с моками LLM/retrieval |

## Команды разработки

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload                                # запуск API
celery -A worker.celery_app worker --loglevel=info           # запуск worker
alembic upgrade head                                         # миграции
pytest tests/ -v                                             # тесты
```

Makefile: `make init-db`, `make create-admin`, `make ingest`, `make ingest-dry`, `make import-whmcs`, `make import-whmcs-dry`. Полный стек: `docker-compose up -d`.

## Конвенции кода (см. `.cursor/rules/project-development.mdc`)

1. **Без хардкода данных** — названия компаний, URL, цены, тексты политик должны браться из config/env/БД, а не зашиваться в код.
2. **Без узких/нишевых правил** — правила должны оставаться общими и масштабироваться на разные домены/тенантов.
3. **LLM — оркестратор** — intent, required_evidence, качество evidence и стратегия retry определяются LLM, а не keyword-правилами.
4. **Всё через конфиг** — поведение в рантайме управляется env-переменными и таблицей БД `app_config` (feature flags).
5. **Следуй существующему стилю** — слоистая архитектура: `api/` → `services/` → `search/` + `db/`; изменения минимальны.

## Правила работы

- Вноси минимальные точечные изменения; не рефактори несвязанный код.
- Запускай `pytest tests/ -v` до и после изменений.
- Не выполняй git-мутации (`commit`, `push`, `reset`, `rebase`) без явного подтверждения пользователя.
