# AGENTS.md — общий навигатор по 6 AI-проектам

Этот файл — контекст для AI-ассистентов, работающих с данным репозиторием. Репозиторий
содержит **6 независимых проектов AI-чатов** и папку `agents_docs/` с подробной
документацией по каждому. Цель файла: по вопросу пользователя сразу определить проект и
не блуждать по всем файлам репозитория.

## Структура репозитория

```text
AI-Chatbot/                        # проект 1: исходники
GroqStreamChain/                   # проект 2: исходники
llm-council-karpathy/              # проект 3: исходники
openai-responses-python-quickstart/# проект 4: исходники
Quorum/                            # проект 5: исходники
rag-knowledge-base-chatbot/        # проект 6: исходники
agents_docs/                       # ЕДИНЫЙ ИСТОЧНИК ИСТИНЫ: документация по всем 6 проектам
├── README.md                      # сводный обзор всех проектов
├── AGENTS.md                      # детальный навигатор (655 строк, самый полный)
├── AGENTS-short.md                # краткая версия навигатора
├── AI-Chatbot/01..10_*.md         # документация проекта 1
├── GroqStreamChain/01..07_*.md    # документация проекта 2
└── ... (по папке на проект)
```

## Правила работы

1. **Сначала определи проект по ключевым словам** (таблица маршрутизации ниже). Не читай
   папки других проектов, если вопрос не про них.
2. **Документация первична.** Для каждого проекта в `agents_docs/<проект>/` лежат файлы по
   единому шаблону:
   - `01_project_structure.md` — карта проекта, дерево каталогов
   - `02_architecture.md` — архитектура, паттерны, конфигурация
   - `03_execution_flow.md` — жизненный цикл запроса, роутинг, ошибки
   - `04_code_quality.md` — техдолг, безопасность, узкие места
   - `05_optimization_roadmap.md` — план рефакторинга P0–P3
   - `06_*report.md` — фронтенд
   - `07_*report.md` — AI-модели и провайдеры
   - `08+` — примеры кода, модели, возможности (набор зависит от проекта)
   Плюс в каждой папке: `README.ru.md` и `AGENTS.ru.md` (инструкции уровня проекта).
3. **Порядок чтения:** профиль проекта здесь → `02_architecture.md` → `03_execution_flow.md`
   → конкретный исходный файл. Для вопросов о моделях — `07_*` (или `10_*` для AI-Chatbot).
4. **Проверяй существование файлов.** Перед правкой кода убедись, что описанный путь
   реально есть в рабочем дереве — часть структуры известна только из документации.
5. **Не выдавай roadmap за готовую функциональность.** Документация различает: работающий
   код, примеры (`08_*`), планы (`05_*`) и заявленные, но не подключённые возможности.
   Особенно: tools в Quorum, vector search в Quorum, image generation в OpenAI quickstart.
6. **Не переносить свойства одного проекта на другой.** WebSocket есть в GroqStreamChain и
   Quorum, но не в AI-Chatbot. RAG есть только в rag-knowledge-base-chatbot.
7. **Минимальные изменения кода**, следуй стилю проекта; аналитические документы в
   `agents_docs/` не редактируй без явного запроса.

## Таблица маршрутизации: ключевые слова → проект

| Ключевые слова вопроса | Проект |
|---|---|
| GitHub Models, `GITHUB_TOKEN`, FastAPI-Users, JWT/Cookie, SQLite, простой чат, glassmorphism | `AI-Chatbot/` |
| Groq, `GROQ_API_KEY`, WebSocket `/ws/chat`, стриминг чанков, `MODEL_NAME`, in-memory сессии | `GroqStreamChain/` |
| совет моделей, council, Stage 1/2/3, Chairman, анонимное ранжирование, `FINAL RANKING`, Street Cred, OpenRouter | `llm-council-karpathy/` |
| OpenAI Responses API, `responses.create`, `iterate_stream`, HTMX, MCP approval, computer use, Vector Store, Whisper | `openai-responses-python-quickstart/` |
| Quorum, NoOversight, `TaskOrchestrator`, sub-agents, делегирование, `AgentFactory`, pgvector, трекинг токенов | `Quorum/` |
| RAG, база знаний, BM25, OpenSearch, Qdrant, citations, `QuerySpec`, WHMCS, ingestion, Celery, support-чатбот | `rag-knowledge-base-chatbot/` |

Если вопрос сравнительный («чем отличается X от Y», «где реализовано Z») — используй разделы
всех затронутых проектов и явно укажи, где что реализовано.

---

## Карта проектов (краткие профили)

### 1. AI-Chatbot — `AI-Chatbot/`

**Что делает:** монолитный AI-чат с регистрацией/логином. Один запрос → один ответ одной
модели. Без истории диалога, без стриминга, без RAG и агентов.

- **LLM:** GitHub Models API (`https://models.github.ai/inference/`, OpenAI-compatible),
  модель `openai/gpt-4o`, клиент `AsyncOpenAI` с кастомным `base_url`. Секрет: `GITHUB_TOKEN`.
- **Бэкенд:** Python 3.13, FastAPI, SQLAlchemy 2.0 async + `aiosqlite` (SQLite), Alembic,
  FastAPI-Users (JWT + cookie), pydantic-settings. Пакеты: `uv`.
- **Фронтенд:** Jinja2 SSR, Tailwind CSS (CDN), vanilla JS, glassmorphism.
- **Ключевые пути:** `app/main.py`, `app/api/v1/chat.py` (`POST /api/chat`),
  `app/services/chat.py` (вызов LLM), `app/core/config.py`, `app/templates/index.html`.
- **Известные ограничения:** нет истории/стриминга/тестов/CI, XSS через `innerHTML`,
  небезопасный default `SECRET`, model и base_url захардкожены.
- **Доку:** `agents_docs/AI-Chatbot/` (файлы 01–10, включая `10_models_and_providers.md`).

### 2. GroqStreamChain — `GroqStreamChain/`

**Что делает:** real-time чат с потоковой передачей токенов через WebSocket. История сессий
только в памяти процесса (теряется при рестарте).

- **LLM:** Groq Cloud, нативный SDK `groq` (синхронный вызов обёрнут в `asyncio.to_thread`).
  Модель через `MODEL_NAME` в `.env` (default `llama-3.1-8b-instant`). Секрет: `GROQ_API_KEY`.
- **Бэкенд:** Python, FastAPI, WebSocket `WS /ws/chat`, JSON-фреймы
  (`session_id`, `initial_message`, `message_received`, `stream`, `stream_end`, `error`).
- **Фронтенд:** статические HTML/CSS/vanilla JS, reconnect с backoff.
- **Ключевые пути:** `server.py`, `config.py`, `system_prompts.py`, `models/chat.py`,
  `services/llm_service.py`, `static/js/main.js`.
- **Известные ограничения:** нет auth/БД/rate limiting/tools/RAG, system prompt мутирует
  историю, утечка памяти по отключённым сессиям, XSS.
- **Доку:** `agents_docs/GroqStreamChain/` (01–07).

### 3. llm-council-karpathy — `llm-council-karpathy/`

**Что делает:** «Совет LLM» (идея Karpathy). Три стадии: (1) несколько моделей параллельно
отвечают, (2) анонимно рецензируют и ранжируют ответы друг друга, (3) модель-председатель
синтезирует финальный ответ.

- **LLM:** OpenRouter (один ключ `OPENROUTER_API_KEY`). Совет в `backend/config.py`:
  `COUNCIL_MODELS` = GPT-5.1, Gemini 3 Pro, Claude Sonnet 4.5, Grok 4;
  `CHAIRMAN_MODEL` = Gemini 3 Pro. Актуальность model ID проверять — список меняется.
- **Бэкенд:** Python 3.10+, FastAPI, `httpx` (async, параллельные вызовы), SSE-стриминг
  (события `stage1_start`…`complete`, `error`), хранение в JSON `data/conversations/`.
- **Фронтенд:** React 19 + Vite 7, react-markdown, ручной SSE-парсер.
- **Ключевые пути:** `backend/main.py`, `backend/council.py` (3 стадии, ranking),
  `backend/openrouter.py` (единственный HTTP-клиент), `backend/config.py`, `frontend/src/App.jsx`.
- **Известные ограничения:** нет auth/БД/tools/настоящего token streaming, JSON пишется
  неатомарно, риск path traversal через `conversation_id`.
- **Доку:** `agents_docs/llm-council-karpathy/` (01–07).

### 4. openai-responses-python-quickstart — `openai-responses-python-quickstart/`

**Что делает:** шаблон чата на OpenAI **Responses API** (преемник Assistants API). Сервер —
тонкий посредник; состояние диалога хранится на стороне OpenAI (Conversations API).

- **LLM:** только OpenAI, SDK `openai>=2.0` (`AsyncOpenAI`). Модель в `.env`
  (`RESPONSES_MODEL`, default `gpt-5-mini`), аудио — `whisper-1`. Секрет: `OPENAI_API_KEY`.
- **API:** Responses, Conversations, Items, Files, Vector Store, Audio Transcriptions.
- **Инструменты:** code interpreter, file search, custom functions (JSON Schema), MCP
  (с approval-флоу), web search, computer use (Playwright). Image generation описана, но
  README заявляет её неподдерживаемой — считать расхождением.
- **Бэкенд:** Python 3.12+, FastAPI, Jinja2, SSE, playwright, pydantic, uvicorn.
- **Фронтенд:** Jinja2 + HTMX + sse.js, инкрементальный Markdown (`stream-md.js`), голосовой
  ввод (`audio-recorder.js`), DOMPurify.
- **Ключевые пути:** `main.py`, `routers/chat.py` (SSE state machine, tools),
  `routers/setup.py` (настройка через UI `/setup` без рестарта, `.env` + `tool.config.json`),
  `utils/computer_use.py`, `utils/custom_functions.py`, `utils/conversations.py`.
- **Известные ограничения:** нет auth, path traversal/IDOR в file endpoints, гонка при
  мутации `client.base_url`, монолитный `routers/chat.py`. Тесты: live-тесты требуют
  `OPENAI_API_KEY`, остальное `-m "not live"`.
- **Доку:** `agents_docs/openai-responses-python-quickstart/` (01–07).

### 5. Quorum (NoOversight) — `Quorum/`

**Что делает:** мульти-агентная платформа. Main agent получает задачу и: отвечает сам
(Solo), строит план делегирования, создаёт специализированных sub-agents (Claude/GPT),
проводит до 3 раундов конференции и синтезирует финальный ответ.

- **LLM:** OpenRouter через `langchain-openai.ChatOpenAI` (base_url → OpenRouter), async
  `ainvoke`/`astream`. Карта моделей (`AgentFactory.MODEL_MAP`): main —
  `anthropic/claude-3.5-sonnet`, sub-agents — `claude-3-5-haiku`, `openai/gpt-4o`.
  Секрет: `OPENROUTER_API_KEY`.
- **Бэкенд:** Python 3.13, FastAPI, LangChain, PostgreSQL + pgvector, Alembic,
  WebSocket (основной транспорт) + SSE (fallback `POST /api/task/stream`),
  `TokenTrackingCallback` (in-memory трекинг токенов/стоимости), structlog,
  search-провайдеры DuckDuckGo/Tavily/SerpAPI.
- **Фронтенд:** React 18 + TypeScript + Vite, Zustand (slices: stream, messages, agents,
  conversations, settings, history), Tailwind, Framer Motion, react-markdown.
- **Ключевые пути:** `backend/src/app.py`, `backend/src/core/orchestrator/task_orchestrator.py`,
  `backend/src/agents/base_agent.py`, `backend/src/agents/agent_factory.py`,
  `backend/src/api/routes/websocket.py`, `backend/src/tools/`,
  `frontend/src/store/slices/streamSlice.ts`.
- **Известные ограничения:** sub-agents выполняются последовательно (не `asyncio.gather`),
  автоматический tool-calling цикл не реализован, vector search не подключён в основном
  потоке, token tracking теряется при рестарте, нет auth, `create_all` вместо миграций.
- **Доку:** `agents_docs/Quorum/` (01–09, включая `09_capabilities_multiagent.md`).

### 6. rag-knowledge-base-chatbot — `rag-knowledge-base-chatbot/`

**Что делает:** enterprise RAG-чатбот поддержки. Отвечает по базе знаний с цитатами и
confidence; при нехватке доказательств — уточняющий вопрос (`ASK_USER`) или эскалация
(`ESCALATE`). База: документы, краулер WHMCS-тикетов, непрерывное обучение на одобренных
тикетах. Это **не** council и не multi-agent: роли LLM связаны детерминированным
оркестратором (state machine).

- **LLM:** OpenAI + любой OpenAI-compatible через `base_url`, единый шлюз `LLMGateway`.
  Модели: `gpt-5.2` (generation/self-critic), `gpt-4o-mini` (нормализация/роутинг/evidence),
  `gpt-3.5-turbo` (fallback), `text-embedding-3-small` (1536 dims), rerankers:
  локальный `cross-encoder/ms-marco-MiniLM-L-6-v2` и Cohere `rerank-multilingual-v3.0`.
  Конфиг модели: environment → app_config (PostgreSQL) → Admin API, смена без redeploy.
- **RAG-пайплайн:** `UNDERSTAND → RETRIEVE → ASSESS_EVIDENCE → DECIDE → GENERATE → VERIFY`.
  RETRIEVE — гибридный: BM25 (OpenSearch) + vector (Qdrant) → RRF → reranker; targeted retry
  до 3 попыток. До 8–10 LLM-ролей на запрос (нормализатор, rewriter, evaluator, decision
  router, generator, self-critic, final polish), каждая роль — строгий JSON-контракт.
- **Инфраструктура:** PostgreSQL 15+ (asyncpg), Redis + Celery (ingestion), MinIO/S3,
  OpenSearch, Qdrant, OpenTelemetry + Prometheus, structlog. Docker Compose.
- **Auth:** JWT Bearer + `X-API-Key` (sk_*) + `X-Admin-API-Key`.
- **Ingestion:** `POST /v1/admin/ingest` → Celery → chunking → SHA-256 idempotency →
  PostgreSQL → embeddings → Qdrant + OpenSearch. Краулер WHMCS на Playwright, статусы
  тикетов pending/approved/rejected.
- **Фронтенд:** React 19 + Vite 7 + Tailwind 4 + axios + react-router (админская SPA:
  диалоги, документы, краулинг, дашборд, настройки, API-токены).
- **Ключевые пути:** `app/main.py`, `app/services/answer_service.py`, `app/services/orchestrator.py`,
  `app/services/phases/`, `app/services/llm_gateway.py`, `app/services/normalizer.py`,
  `app/search/`, `app/crawlers/whmcs.py`, `worker/tasks.py`, `app/api/routes/`.
- **Известные ограничения:** крупные модули, SSRF-риски в fetch/crawl, OpenSearch security
  отключён в compose, rate limit fail-open при недоступном Redis, default `JWT_SECRET`
  небезопасен, «псевдостриминг» (ответ отдаётся кусками после полного выполнения пайплайна).
- **Доку:** `agents_docs/rag-knowledge-base-chatbot/` (01–08).

---

## Сравнительная таблица

| Критерий | AI-Chatbot | GroqStreamChain | LLM Council | OpenAI Responses | Quorum | RAG Chatbot |
|---|---|---|---|---|---|---|
| Моделей | 1 (GPT-4o) | 1 (Groq) | 4+ (совет) | 1 (OpenAI) | N (агенты) | мульти-роль, 1 провайдер |
| Мультиагентность | нет | нет | совет моделей | нет | да (оркестратор) | мульти-ролевой пайплайн |
| RAG | нет | нет | нет | file search (OpenAI) | web search (не подключён) | да (гибридный) |
| Стриминг | нет | WebSocket | SSE | SSE | WebSocket + SSE | SSE (псевдо) |
| Auth | JWT (FastAPI-Users) | нет | нет | нет | нет | JWT + API-key + Admin |
| Хранилище | SQLite | in-memory | JSON-файлы | сторона OpenAI | PostgreSQL | PG + OpenSearch + Qdrant |
| Фронтенд | Jinja2 + Tailwind | Vanilla JS | React 19 + Vite | Jinja2 + HTMX | React 18 + TS + Zustand | React 19 + Vite |
| Сложность | низкая | низкая | средняя | средняя | высокая | очень высокая |

## Общее для всех проектов

- Бэкенд везде — **FastAPI** (Python 3.10–3.13), пакеты через `uv` (фронтенды — `npm`).
- Лицензия MIT. Документация на русском (`*.ru.md` / `*_RU.md`) и английском (`*.md`).
- Документация во всех проектах построена по единому нумерованному шаблону (см. выше).
