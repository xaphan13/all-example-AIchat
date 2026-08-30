# AGENTS.ru.md

> **Единый источник истины для AI-ассистентов.**
> Этот файл читают все харнесы (Claude Code, Cursor, Aider, Gemini и др.).
> Русская версия. English version: [AGENTS.md](AGENTS.md).

---

### Что это за проект?

**NoOversight (Quorum)** — production-ready платформа для мульти-агентного взаимодействия
AI-моделей. Несколько LLM-агентов (Claude, GPT, Gemini, Grok) коллаборируют над сложными
задачами через единый OpenRouter API. Интеллектуальный оркестратор делегирует подзадачи
специализированным агентам и синтезирует их ответы. Архитектура — streaming-first,
event-driven, с real-time обратной связью через WebSocket и SSE.

### Читайте папку `docs/` В ПЕРВУЮ ОЧЕРЕДЬ — не обходите весь репозиторий

Перед изучением исходного кода прочитайте аналитические документы в [`docs/`](docs/). Это
единый источник истины, написанный специально, чтобы избежать слепого обхода всего проекта:

| Файл | Содержание |
|---|---|
| [`docs/01_project_structure.md`](docs/01_project_structure.md) | Полное дерево директорий, описание каждого ключевого файла, зависимости, стек |
| [`docs/02_architecture.md`](docs/02_architecture.md) | Слоистая архитектура, паттерны, поток данных, схема БД, безопасность |
| [`docs/03_execution_flow.md`](docs/03_execution_flow.md) | Жизненный цикл приложения, бизнес-процессы, роутинг, протокол WebSocket, ошибки, логирование |
| [`docs/04_code_quality.md`](docs/04_code_quality.md) | Аудит SOLID/DRY/KISS, техдолг, мёртвый код, запахи кода, узкие места, пробелы безопасности |
| [`docs/05_optimization_roadmap.md`](docs/05_optimization_roadmap.md) | Приоритизированные улучшения, фиксы производительности, план рефакторинга, фазы, оценки |

**Порядок работы для любой задачи:**
1. Найдите релевантный раздел в `docs/` (структура/архитектура/поток/качество/roadmap).
2. Только после этого открывайте конкретные исходные файлы, упомянутые там.
3. Не рекурсивно листайте и не читайте целиком `backend/src/` или `frontend/src/` — дерево
   уже задокументировано в `docs/01`.

### Стек технологий (кратко)

- **Backend:** Python 3.13+, FastAPI, async/await, LangChain (`langchain-openai` → OpenRouter),
  SQLAlchemy 2.0 (async), Alembic, PostgreSQL 13+ с pgvector, structlog, WebSocket + SSE.
- **Frontend:** React 18, TypeScript 5.5, Vite 5, Zustand 4 (slices + нормализованное состояние),
  Tailwind CSS 3, Framer Motion, react-markdown.
- **Внешние сервисы:** OpenRouter (доступ к LLM), OpenAI (embeddings), DuckDuckGo/Tavily/SerpAPI (web search).

### Структура проекта (верхний уровень)

```
Quorum/
├── backend/    # FastAPI backend (Python, async) — полное дерево в docs/01
├── frontend/   # React 18 + TypeScript SPA — полное дерево в docs/01
├── docs/       # Аналитические документы (читать в первую очередь)
├── scripts/    # Shell-скрипты запуска/остановки сервисов
├── Makefile    # Корневой: install, start, stop, dev, test, lint, build
└── pyproject.toml
```

### Конвенции и стиль кода

- **Слои backend:** `api/` (роуты) → `core/` (бизнес-логика, оркестратор) →
  `agents/` (LLM-клиенты) → `infrastructure/` (БД, WS, логирование, трекинг) → `tools/`.
  Соблюдайте слои; роуты не должны вызывать репозитории для сквозной логики — используйте сервисы.
- **Async везде** на backend. Используйте `async def`, `AsyncSession`, `asyncio.gather`.
  Не блокируйте event loop.
- **Pydantic** для всех моделей запросов/ответов и настроек (`pydantic-settings`).
- **Репозитории** принимают `AsyncSession` снаружи; они не управляют жизненным циклом сессии.
- **Синглтоны** — глобальные переменные модулей (`db_manager`, `connection_manager`, `settings`,
  `get_token_manager()`, `get_settings_service()`, `get_tool_registry()`).
- **Состояние frontend:** Zustand со slices и нормализованным состоянием (`byId`/`allIds`).
  Все WS-события идут через единый `handleStreamEvent` в `streamSlice.ts` (event sourcing).
- **Именование:** backend `snake_case`, frontend `camelCase` (Pydantic `alias_generator = to_camel`).
- **Логирование:** структурированное (`structlog` backend, кастомный `Logger` frontend) с
  correlation ID. Чувствительные данные (API-ключи, токены) редактируются автоматически —
  никогда не логируйте сырые секреты.

### Запуск и тестирование

```bash
make install     # установить зависимости backend + frontend
make dev         # запустить оба сервиса (backend :8000, frontend :5173)
make test        # backend pytest
make lint        # линтеры backend + frontend
make build       # production-сборка frontend
```

Тесты backend: `cd backend && pytest`. У frontend пока нет test-скрипта (см. `docs/05`).

### Известные подводные камни (детали в `docs/04`)

- `ARCHITECTURE.md` и `README.md` местами устарели (упоминают LiteLLM / несуществующие
  эндпоинты). Доверяйте `docs/`, а не им.
- `health.py` обращается к несуществующим полям settings — health check некорректен.
- `_execute_sub_agents` (параллельный режим) — мёртвый код; реальный путь — последовательный
  `_run_agent_conversation`.
- Tool calling декларирован (схемы передаются в ChatOpenAI), но **не исполняется** —
  `BaseAgent.execute_tool()` не вызывается из цикла стриминга.
- Значения enum `AgentType` не соответствуют model ID в `MODEL_MAP`.
- Token usage хранится только in-memory — теряется при рестарте.
- Нет аутентификации, нет rate limiting — не деплойте публично без Phase 3 из `docs/05`.

### Правила для AI-ассистентов

1. **Сначала читайте `docs/`**, открывайте исходники только по необходимости.
2. Вносите **минимальные** изменения; следуйте существующему слоению и именованию.
3. Код backend — async; не блокируйте event loop.
4. Не правьте `docs/` без явного запроса — это аналитический снапшот (август 2026).
5. После изменений backend запускайте `make test` / `make lint` при возможности.
6. Не делайте commit/push без явного подтверждения пользователя.
