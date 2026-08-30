# Карта шести AI-проектов

Этот файл — общий контекст для AI-агентов, которые отвечают на вопросы по проектам в текущем репозитории. В шести соседних папках собрана документация о шести разных приложениях, связанных с LLM-чатами, AI-ассистентами, мультиагентными системами и RAG.

## Как использовать этот файл

1. Сначала определи, о каком проекте идёт речь. Если пользователь не назвал проект явно, сопоставь вопрос с назначением и особенностями ниже.
2. Затем изучи документацию внутри соответствующей папки:
   - `README*.md` — запуск и общий сценарий;
   - `AGENTS*.md` и `CLAUDE*.md` — правила работы с документацией и архитектурные указания;
   - нумерованные отчёты `01_*.md`, `02_*.md` и далее — детальная структура, архитектура, поток выполнения, AI-модели, frontend и roadmap.
3. Если вопрос касается нескольких проектов, сравни их явно и не смешивай компоненты, модели, порты и команды запуска.
4. Разделяй фактическое текущее состояние, заявленные возможности и предложения roadmap. Если документация противоречива, укажи это пользователю.
5. Не утверждай, что модель, endpoint, тест, файл или функция реально работают, если документация говорит только о планах или обнаруживает мёртвый/неиспользуемый код.
6. Названия папок, файлов, классов, маршрутов, переменных окружения и команд оставляй в оригинальном виде.

Документация может быть неполной или устаревшей. Если сведений в отчётах нет, так и сообщай: «в документации не указано» или «не подтверждено документацией».

## Быстрый выбор проекта

| Папка | Короткое описание | Главный отличительный признак |
|---|---|---|
| `AI-Chatbot/` | Простой авторизованный веб-чат | FastAPI + Jinja2, один запрос к одной модели, GitHub Models |
| `GroqStreamChain/` | Real-time чат с потоковой генерацией | WebSocket и streaming через Groq |
| `llm-council-karpathy/` | Совет LLM | Несколько моделей отвечают, рецензируют ответы и выбирают итог |
| `openai-responses-python-quickstart/` | Расширенный starter на Responses API | OpenAI Responses API, SSE, файлы, голос и инструменты |
| `Quorum/` | Мультиагентный AI-чат | Main agent делегирует задачи sub-agents и проводит конференцию |
| `rag-knowledge-base-chatbot/` | Support-чат по базе знаний | Гибридный RAG, citations, reviewer и решения PASS/ASK_USER/ESCALATE |

---

## 1. `AI-Chatbot/`

### Назначение

Полноценный, но простой авторизованный веб-чат с одной LLM. Это монолитное FastAPI-приложение с серверным рендерингом через Jinja2. Сценарий — один пользовательский запрос и один ответ одной модели.

Это **не** мультиагентная система, **не** RAG и **не** платформа с памятью диалога.

### Технологии и архитектура

- Python `>=3.13`, `uv`.
- FastAPI, FastAPI-Users, JWT/Cookie-аутентификация.
- SQLAlchemy 2.0 async, `aiosqlite`, SQLite, Alembic.
- Pydantic v2 и `pydantic-settings`.
- Jinja2, HTML5, Tailwind CSS через CDN, Lucide Icons через CDN, vanilla JavaScript.
- SSR/MPA; отдельного SPA, npm-проекта и frontend-сборки нет.

### LLM и поток запроса

Фактически подключены GitHub Models API и OpenAI-compatible SDK `AsyncOpenAI`:

- Base URL: `https://models.github.ai/inference/`;
- модель: `openai/gpt-4o`;
- ключ: `GITHUB_TOKEN` с правом `models:read`.

Поток: авторизованный клиент отправляет `POST /api/chat` с `{ "prompt": "..." }`; FastAPI проверяет JWT в cookie; `app/services/chat.py` вызывает модель; клиент получает `{ "response": "..." }`.

История сообщений не хранится и повторно не отправляется модели. Нет streaming, WebSocket, SSE, tool calling, файлов, RAG, выбора модели, retry и полноценной обработки ошибок LLM. Другие провайдеры упоминаются только как будущие варианты.

### Основные маршруты

- `GET /` — landing page;
- `GET /login`, `GET /signup`, `GET /chat`;
- `POST /auth/register`, `POST /auth/login`, `POST /auth/logout`;
- `POST /api/chat`;
- `GET/PATCH /users/me`;
- `GET /health`, `GET /docs`.

### Важные файлы

- `app/main.py` — приложение, HTML-роуты, API и StaticFiles;
- `app/api/v1/chat.py` — chat endpoint;
- `app/api/v1/users.py` — auth и user routes;
- `app/services/chat.py` — вызов GitHub Models;
- `app/core/config.py` — конфигурация;
- `app/db/`, `app/models/`, `app/schemas/` — БД, ORM и DTO;
- `app/templates/` — `landing.html`, `login.html`, `signup.html`, `index.html`;
- `alembic/` — миграции.

### Запуск

```bash
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Ожидаемые переменные: `GITHUB_TOKEN`, `SECRET`, `DATABASE_URL`, `DEBUG`.

Документация отмечает критический нюанс: `app/main.py` монтирует `app/static`, но наличие этой директории не подтверждено. Это может блокировать запуск. Также в документации расходятся имя SQLite-файла и некоторые детали конфигурации.

---

## 2. `GroqStreamChain/`

### Назначение

Демонстрационный real-time текстовый чат с потоковым ответом. Браузер держит WebSocket-соединение, сервер отправляет запрос в Groq и возвращает фрагменты ответа по мере генерации.

Это **одномодельный чат**, а не мультиагентная система. История сессии живёт только в памяти процесса.

### Технологии и архитектура

- Python; версия в документации противоречива: указаны 3.9+, 3.12+ и `pyproject.toml`/`.python-version` с 3.13.
- FastAPI, Uvicorn, WebSocket, Pydantic, `python-dotenv`, Jinja2.
- Официальный Groq SDK.
- HTML/CSS/vanilla JavaScript без React, Vue и frontend-сборки.
- LangChain и `langchain-groq` присутствуют в зависимостях, но рабочий вызов использует Groq SDK. `ChatGroq` и часть LangChain-кода описаны как неиспользуемые.

### LLM и протокол

Реальный провайдер — Groq Cloud API. Ключ: `GROQ_API_KEY`. Модель задаётся через `MODEL_NAME`; в документации моделью по умолчанию названа `llama-3.1-8b-instant`. Также упоминаются другие модели Groq, но их актуальность нужно сверять с каталогом Groq.

Основной маршрут — `WS /ws/chat`. Клиент отправляет `{"message": "..."}`. Сервер создаёт UUID-сессию, сохраняет историю, вызывает `Groq.chat.completions.create(stream=True)` через `asyncio.to_thread` и посылает события `stream` с частями текста, затем `stream_end`.

### Основные файлы

- `server.py` — FastAPI, HTTP, WebSocket, `ConnectionManager` и сессии;
- `config.py` — настройки;
- `system_prompts.py` — системный промпт;
- `models/chat.py` — `Message`, `ChatSession`, `ChatRequest`;
- `services/llm_service.py` — Groq и streaming;
- `templates/index.html` — интерфейс;
- `static/js/main.js` — WebSocket, chunks и reconnect;
- `static/css/style.css` — стили;
- `test_groq.py` — ручная проверка API, не полноценный pytest-набор.

### Запуск

```bash
pip install -r requirements.txt
python server.py
```

или:

```bash
uv sync
uv run python -m server
```

Адрес по умолчанию: `http://localhost:8000`. В `.env` требуется `GROQ_API_KEY`; в документации также встречается `MODEL_NAME`.

### Ограничения

- история теряется при рестарте;
- отключённые сессии могут оставаться в памяти;
- системный промпт может повторно накапливаться в истории;
- нет auth, rate limiting, полноценного retry, graceful shutdown и production-хранилища;
- отмечен XSS-риск из-за `innerHTML`;
- автоматических unit/integration-тестов нет;
- reconnect клиента не означает восстановление серверной сессии.

---

## 3. `llm-council-karpathy/`

### Назначение

Локальное веб-приложение «совет LLM», похожее на ChatGPT. Несколько моделей независимо отвечают на вопрос, затем анонимно рецензируют и ранжируют ответы, после чего chairman synthesizes итоговый ответ.

Это мультимодельный и частично мультиагентный workflow, но не автономная агентная платформа: нет инструментов, долговременной памяти, планирования и динамической оркестрации.

### Технологии и архитектура

- Backend: Python 3.10, FastAPI, Uvicorn, `httpx`, Pydantic, `python-dotenv`.
- Frontend: React 19, Vite 7, JSX/JavaScript, `react-markdown`.
- REST API и SSE для передачи прогресса стадий.
- Хранилище: локальные JSON-файлы в `data/conversations/`; БД, Redis и broker отсутствуют.

### AI-пайплайн

Единственный провайдер — OpenRouter: `https://openrouter.ai/api/v1/chat/completions`.

Документированный состав совета:

```python
COUNCIL_MODELS = [
    "openai/gpt-5.1",
    "google/gemini-3-pro-preview",
    "anthropic/claude-sonnet-4.5",
    "x-ai/grok-4",
]
CHAIRMAN_MODEL = "google/gemini-3-pro-preview"
```

Модель заголовков — `google/gemini-2.5-flash`.

Стадии:

1. **Stage 1** — четыре модели параллельно отвечают на исходный вопрос.
2. **Stage 2** — ответы переименовываются в `Response A/B/C...`; модели анонимно рецензируют и ранжируют их. Из текста извлекается `FINAL RANKING:`; рассчитывается `Street Cred`.
3. **Stage 3** — chairman получает вопрос, ответы и рецензии с именами моделей и создаёт финальный ответ.

SSE стримит прогресс стадий, а не токены отдельных LLM в реальном времени.

### Важные файлы и запуск

- `backend/config.py` — модели и настройки;
- `backend/main.py` — FastAPI, REST и SSE;
- `backend/openrouter.py` — OpenRouter и параллельные запросы;
- `backend/council.py` — стадии, промпты, рейтинги и агрегация;
- `backend/storage.py` — JSON CRUD;
- `frontend/src/App.jsx`, `api.js`, `components/Stage1.jsx`, `Stage2.jsx`, `Stage3.jsx` — UI.

```bash
uv sync
uv run python -m backend.main

cd frontend
npm install
npm run dev
```

Backend работает на `http://localhost:8001`, frontend — на `http://localhost:5173`. Нужен `OPENROUTER_API_KEY` в `.env`. Также описан запуск через `./start.sh`.

### Ограничения и нюансы

- UI фактически single-turn, хотя backend хранит conversation history;
- `label_to_model` и рейтинги не сохраняются в JSON, поэтому после перезагрузки теряются деанонимизация и `Street Cred`;
- модели и chairman захардкожены;
- парсинг зависит от формата `FINAL RANKING:`;
- нет auth, rate limiting, retry/backoff и полноценного тестового набора;
- ручной SSE-парсер frontend может некорректно обрабатывать сетевые chunks;
- актуальность перечисленных model IDs документацией не проверена.

---

## 4. `openai-responses-python-quickstart/`

### Назначение

Starter/template для чат-приложений на OpenAI Responses API (`/v1/responses`). Это серверно-рендеримое приложение с потоковыми ответами, мультимодальным вводом и набором инструментов.

Сервер является proxy/orchestrator между браузером и OpenAI. Состояние диалога хранится через OpenAI Conversations API, а конфигурация ассистента — локально. Это **не** мультиагентная система.

### Технологии и архитектура

- Python 3.13, FastAPI, официальный `openai>=2.0.0`, `AsyncOpenAI`, Jinja2, Pydantic, `asyncio`.
- HTMX и HTMX SSE extension, vanilla JavaScript/CSS.
- `marked.js` и `DOMPurify` через CDN.
- SSE, без React/Vue, npm-проекта и SPA-сборки.
- Playwright + Chromium для computer use.

### LLM, данные и инструменты

Провайдер — только OpenAI. Модель по умолчанию — `gpt-5-mini`; выбор выполняется в `/setup`. Документация перечисляет модели GPT-4.x, o-серии, GPT-5 и `gpt-oss`; список захардкожен. Для аудио используется `whisper-1`.

Путь сообщения:

1. `POST /chat/{conversation_id}/send` принимает сообщение.
2. Изображения загружаются в OpenAI Files API с `purpose="vision"`.
3. Сообщение записывается в OpenAI Conversation.
4. `GET /chat/{conversation_id}/receive` открывает SSE-поток.
5. Сервер вызывает `responses.create(stream=True)` и преобразует события в SSE.
6. Браузер накапливает текст, рендерит Markdown и санитизирует его через `DOMPurify`.
7. После tool calls результаты записываются в Conversation, а Responses API вызывается снова.

Поддерживаемые типы инструментов:

- Code Interpreter;
- File Search и Vector Stores;
- Web Search;
- Image Generation;
- custom Python functions;
- MCP с approve/reject;
- Computer Use через headless Playwright.

Custom functions выполняются параллельно, computer-use-вызовы — последовательно.

### Важные файлы и запуск

- `main.py` — FastAPI, lifespan и роутеры;
- `routers/chat.py`, `setup.py`, `files.py`, `audio.py`;
- `utils/function_calling.py`, `function_definitions.py`, `computer_use.py`, `config.py`;
- `templates/` — chat/setup/SSE-компоненты;
- `static/stream-md.js`, `audio-recorder.js`;
- `tool.config.json` — custom functions и MCP;
- `tests/` — unit/integration/Playwright/live tests.

```bash
uv sync
uv run uvicorn main:app --reload
uv run playwright install chromium
```

Адрес: `http://localhost:8000`. Нужны `OPENAI_API_KEY` и `RESPONSES_MODEL` в `.env`.

Проверки:

```bash
uv run ruff check
uv run ty check
uv run pytest -m "not live"
```

### Ограничения и риски

- только OpenAI, без абстракции провайдеров;
- один глобально настроенный ассистент, без per-conversation configuration;
- нет auth и authorization, проект рассчитан прежде всего на локальный запуск;
- нет базы данных, broker или внешнего кэша;
- отсутствует SSE heartbeat/reconnect;
- отмечены риски path traversal, race condition при работе с `base_url` и небезопасной записи `.env`;
- генерация изображений заявлена, но полноценная поддержка шаблоном не подтверждена;
- `utils/threads.py` — legacy-код для Assistants API, его не следует считать рабочим путём.

---

## 5. `Quorum/`

### Назначение

Production-oriented платформа мультиагентного AI-чата с двумя режимами:

- **Solo** — ответ одного основного агента;
- **Quorum** — main agent анализирует задачу, делегирует подзадачи специализированным sub-agents, проводит конференцию и синтезирует итог.

Архитектура описана как asynchronous, streaming-first и event-driven. Это наиболее явно мультиагентный проект среди шести, но документация отмечает расхождения между заявленной архитектурой и фактическим runtime-путём.

### Технологии и архитектура

Backend:

- Python 3.13+; README допускает Python 3.11+;
- FastAPI, Uvicorn, `asyncio`;
- LangChain `langchain-openai` с OpenRouter;
- SQLAlchemy async, `asyncpg`, Alembic, PostgreSQL 13+, pgvector;
- Pydantic, `structlog`, correlation ID;
- WebSocket и SSE;
- `BaseTool`, `ToolRegistry`, `WebSearchTool`;
- Redis заявлен как optional, но фактически не используется.

Frontend:

- React 18, TypeScript 5.5, Vite 5;
- Zustand, Tailwind CSS, Framer Motion;
- `react-markdown`, `remark-gfm`, jsPDF;
- SPA/CSR без SSR и Jinja2.

### AI-поток

Единая точка доступа к LLM — OpenRouter: `https://openrouter.ai/api/v1`.

Фактический `AgentFactory.MODEL_MAP` документирован так:

- main agent: `anthropic/claude-3.5-sonnet`;
- sub-agent: `anthropic/claude-3-5-haiku`;
- sub-agent: `openai/gpt-4o`.

В документации также встречаются другие marketing/model IDs; не следует считать их фактическим runtime-составом без проверки кода.

Поток:

1. Frontend отправляет задачу через `WS /ws`.
2. Backend создаёт/загружает conversation и сохраняет user message.
3. `TaskOrchestrator` создаёт main agent.
4. В режиме Quorum main agent строит JSON-план делегирования.
5. `AgentFactory` создаёт sub-agents.
6. Проходит до трёх раундов обсуждения.
7. События agent messages отправляются frontend в streaming-режиме.
8. Main agent получает контекст конференции и синтезирует финальный ответ.
9. Callbacks считают token usage и стоимость.

Важно: несмотря на заявленную возможность параллельной работы, текущий путь sub-agents описан как последовательный. Token tracking хранится в памяти процесса.

### Важные файлы и запуск

- `backend/src/app.py` — точка входа;
- `backend/src/core/orchestrator/task_orchestrator.py` — оркестрация;
- `backend/src/agents/base_agent.py`, `agent_factory.py`;
- `backend/src/api/routes/` — tasks, websocket, conversations, settings, tokens, health;
- `backend/src/infrastructure/` — database, tracking, websocket, logging;
- `backend/src/tools/`;
- `frontend/src/store/slices/streamSlice.ts`, `services/websocket.ts`, компоненты agents.

Backend:

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp config/env_template.txt .env
./scripts/setup_postgres.sh
./scripts/init_database.sh
make run
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

Backend: `http://localhost:8000`; frontend: `http://localhost:5173`. Также заявлены `make install`, `make dev`, `make test`, `make lint`, `make build`.

### Возможности и ограничения

Есть PostgreSQL persistence, token/cost analytics, agent panel, WebSocket/SSE, web search, embeddings/pgvector, Markdown/PDF export, structured logging и cancellation.

Но документация отмечает:

- автоматический цикл `tool call → execute → result → повторный вызов` не реализован полностью;
- sub-agents фактически могут работать последовательно;
- embeddings/VectorService не подключены к обычному потоку сохранения сообщений;
- token usage in-memory;
- нет auth, authorization и rate limiting;
- API keys в БД не шифруются;
- health check может ссылаться на несуществующие поля;
- несколько Uvicorn workers несовместимы с process-local WebSocket/token state без Redis/pub-sub;
- README и `ARCHITECTURE.md` местами устарели; для текущего состояния предпочтительны `docs/` и `AGENTS.ru.md`.

---

## 6. `rag-knowledge-base-chatbot/`

### Назначение

Корпоративный RAG-чат-бот для клиентской поддержки. Он отвечает по базе знаний, состоящей из документов, политик, FAQ, прайсов и тикетов WHMCS, и возвращает цитаты, confidence и решение:

- `PASS` — ответить;
- `ASK_USER` — запросить уточнение;
- `ESCALATE` — передать человеку или внешнему агенту.

Поддерживаются многодиалоговый чат, SSE endpoint и stateless `suggested reply` для WHMCS, Zendesk, livechat и других helpdesk-систем.

Это модульный монолит, **не** набор автономных агентов и **не** мультиагентный оркестратор: специализированные LLM-роли обмениваются данными через `OrchestratorContext` под управлением детерминированного pipeline.

### Технологии и инфраструктура

Backend и данные:

- Python 3.11+, FastAPI, Pydantic v2, Uvicorn;
- PostgreSQL 15+;
- Redis для cache, rate limiting и Celery broker;
- Celery для ingestion;
- OpenSearch для BM25;
- Qdrant для vector search;
- MinIO/S3 для исходных документов;
- Playwright/Chromium для WHMCS crawler;
- OpenTelemetry, Prometheus, structured logging.

Frontend:

- React 19, TypeScript, Vite 7;
- Tailwind CSS 4, Axios, React Router 7, `lucide-react`;
- SPA, в production — Nginx.

### LLM и RAG-пайплайн

Основной LLM gateway использует OpenAI Chat Completions API. `base_url` может переопределяться, поэтому архитектура допускает OpenAI-compatible endpoints. Документированные модели: `gpt-5.2`, `gpt-4o-mini`, fallback `gpt-3.5-turbo`; настройки можно менять через env, `app_config` и Admin API без redeploy.

Embeddings: OpenAI `text-embedding-3-small`, 1536 dimensions. Reranking: локальный `cross-encoder/ms-marco-MiniLM-L-6-v2` или Cohere `rerank-multilingual-v3.0`; предусмотрен fallback без reranker.

Поток запроса:

1. Guardrails, prompt-injection check и санитизация.
2. Intent cache и определение языка.
3. LLM-нормализация в `QuerySpec`.
4. State machine: `UNDERSTAND → RETRIEVE → ASSESS → DECIDE → GENERATE → VERIFY`.
5. Параллельный BM25 + vector search, RRF fusion, deduplication, reranking и evidence selection.
6. До нескольких retrieval retries при недостаточном evidence.
7. Генерация ответа и, при необходимости, reasoning prepass/self-critic.
8. Reviewer проверяет claims, grounding, citations и confidence.
9. Final polish формирует ответ и debug payload.

Роли вроде normalizer, query rewriter, evidence evaluator, decision router, generator и reviewer возвращают структурированный JSON. Ingestion принимает JSON, URL, файлы, website crawl, WHMCS tickets и SQL dumps.

### Важные файлы и запуск

- `app/main.py` — приложение и middleware;
- `app/api/routes/` — conversations, reply, documents, tickets, admin, auth, dashboard, health;
- `app/services/answer_service.py` — главная точка входа;
- `app/services/orchestrator.py`, `phases/`, `retrieval.py`, `normalizer.py`, `llm_gateway.py`, `model_router.py`, `reviewer.py`;
- `app/search/` — OpenSearch, Qdrant, embeddings, rerankers;
- `app/db/models.py`, `app/core/`;
- `worker/` — Celery;
- `frontend/src/` — React UI;
- `scripts/` — admin, ingestion, crawler/import;
- `source/` — sample documents and conversations;
- `docker-compose.yml`, Dockerfiles, `nginx/`;
- `tests/` — backend pytest tests.

Docker-запуск:

```bash
cp .env.example .env
docker-compose up -d
docker-compose exec api alembic upgrade head
docker-compose exec api python -m scripts.create_admin_user
docker-compose exec api python -m scripts.ingest_from_source
```

Frontend локально:

```bash
cd frontend
npm install
npm run dev
```

API обычно доступен на `http://localhost:8000`; локальный Vite frontend — на `http://localhost:5173`, Docker frontend — на `http://localhost:5174`.

### Возможности и ограничения

Уникальны hybrid retrieval, citations, claim-level reviewer, confidence calibration, debug payload, WHMCS approval workflow, stateless integration API, offline evaluation и graceful degradation.

Ограничения:

- нет native tool/function calling;
- нет autonomous agents и agent-to-agent workflow;
- custom LLM provider заявлен, но фабрика фактически его не реализует;
- SSE — псевдостриминг: ответ сначала генерируется целиком, затем отправляется кусками примерно по 100 символов;
- frontend tests не подтверждены;
- JWT хранится в `localStorage`, отмечены SSRF и security-риски;
- в Docker OpenSearch security отключён;
- default `JWT_SECRET` небезопасен для production;
- в коде есть технический долг в крупных сервисах и дублирование config/fallback-логики.

---

## Сравнение потоков ответа

- `AI-Chatbot/`: обычный HTTP-запрос → один полный ответ одной модели.
- `GroqStreamChain/`: WebSocket → token/chunk streaming одной модели Groq.
- `llm-council-karpathy/`: REST/SSE → несколько этапов совета; потокится прогресс, не отдельные токены.
- `openai-responses-python-quickstart/`: send + SSE receive → Responses API с tool calls, файлами, голосом и потоковыми событиями.
- `Quorum/`: WebSocket/SSE → делегирование main agent, сообщения sub-agents, синтез.
- `rag-knowledge-base-chatbot/`: RAG state machine → поиск evidence, генерация, reviewer и citations; SSE в текущем описании псевдостриминговый.

## Сравнение хранения состояния

- `AI-Chatbot/`: SQLite хранит пользователей; история чата не хранится.
- `GroqStreamChain/`: история только в памяти процесса.
- `llm-council-karpathy/`: conversations в локальных JSON-файлах.
- `openai-responses-python-quickstart/`: conversations и сообщения в OpenAI Conversations API; локально хранится конфигурация.
- `Quorum/`: conversations/messages в PostgreSQL; token tracking — в памяти.
- `rag-knowledge-base-chatbot/`: PostgreSQL для документов, чатов, сообщений, citations, пользователей и конфигурации; Redis/OpenSearch/Qdrant используются для соответствующих инфраструктурных задач.

## Что не следует путать

- GitHub Models в `AI-Chatbot/` — не то же самое, что OpenRouter в `llm-council-karpathy/` и `Quorum/`.
- Groq streaming в `GroqStreamChain/` — отдельный рабочий путь, несмотря на наличие LangChain-зависимостей.
- `llm-council-karpathy/` использует несколько моделей для совета, но это не тот же оркестратор, что `Quorum/`.
- `openai-responses-python-quickstart/` использует OpenAI Responses API и Conversations API; не переносить его предположения о tool calls на остальные проекты.
- `rag-knowledge-base-chatbot/` имеет несколько LLM-ролей, но это детерминированный RAG pipeline, а не автономные агенты.
- SSE не всегда означает настоящий token streaming: в council и RAG он используется главным образом для прогресса или псевдостриминга.

## Общий порядок ответа на вопросы

При ответе по нескольким проектам полезно указывать:

1. название папки;
2. назначение и тип AI-системы;
3. фактический provider/model и способ вызова;
4. transport: HTTP, WebSocket или SSE;
5. хранение состояния;
6. конкретные файлы и команды запуска;
7. ограничения и степень подтверждённости сведений документацией.

Если пользователь просит изменить код конкретного проекта, сначала проверь инструкции внутри этой папки и затем работай только с затронутым проектом. Этот корневой файл служит картой и справочником, но не заменяет локальные инструкции проекта.
