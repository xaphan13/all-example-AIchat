# AGENTS.md — навигатор по шести AI-проектам

## Назначение файла

Этот файл описывает шесть проектов из текущей рабочей директории. Используй его как карту контекста, когда нужно отвечать на вопросы об архитектуре, LLM, API, frontend, хранении данных, потоковой передаче, RAG или мультиагентной логике.

В каждой папке находятся аналитические Markdown-документы проекта. Основные источники — `01_project_structure.md`, `02_architecture.md`, `03_execution_flow.md`, документы о качестве и оптимизации, отчёты о frontend и моделях, а также `README.ru.md`/`README.md`. Документы находятся непосредственно в папках проектов, а не обязательно в `docs/`, даже если отдельные README ссылаются на `docs/`.

Важно различать:

- **текущую реализацию**, описанную как работающий код;
- **пример или возможный вариант**, приведённый в `08_ai_code_examples.md` или аналогичном файле;
- **roadmap и технический долг**, описанные в `05_optimization_roadmap.md`;
- **заявленную возможность**, которая может быть частично подключена или не использоваться в основном runtime-потоке.

В текущем checkout в основном представлены документы. Описанные исходные каталоги некоторых проектов (`backend/`, `frontend/`, `app/`, `tests/` и т. п.) могут отсутствовать физически. Поэтому перед изменением кода сначала проверяй, присутствует ли исходный файл в рабочем дереве.

---

## Быстрый выбор проекта

| Если вопрос о… | Проект | Главный признак |
|---|---|---|
| Простом защищённом чате с одной моделью | `AI-Chatbot` | FastAPI + Jinja2 + SQLite + GitHub Models |
| Настоящем WebSocket-стриминге ответа | `GroqStreamChain` | FastAPI + WebSocket + Groq + in-memory-сессии |
| Сравнении нескольких моделей и анонимном голосовании | `llm-council-karpathy` | Stage 1 → Stage 2 → Stage 3 через OpenRouter |
| OpenAI Responses API и встроенных инструментах | `openai-responses-python-quickstart` | SSE + HTMX + tools/MCP/computer use |
| Делегировании задач суб-агентам и конференциях | `Quorum` | Main agent + sub-agents + WebSocket + PostgreSQL |
| Ответах по базе знаний с цитатами | `rag-knowledge-base-chatbot` | Hybrid RAG: OpenSearch + Qdrant + PostgreSQL |

### Главное различие между проектами

- `AI-Chatbot` — одномодельный stateless MVP без памяти, RAG и streaming.
- `GroqStreamChain` — одномодельный чат с историей только в памяти процесса и потоковой выдачей через WebSocket.
- `llm-council-karpathy` — несколько заранее заданных моделей независимо отвечают, анонимно рецензируют ответы друг друга, после чего председатель синтезирует результат.
- `openai-responses-python-quickstart` — один OpenAI-ассистент на базе Responses API, Conversations API и набора инструментов.
- `Quorum` — оркестрация main agent и специализированных суб-агентов с раундами обсуждения.
- `rag-knowledge-base-chatbot` — не council и не native multi-agent-система, а управляемый кодом RAG-пайплайн для поддержки по документам и тикетам.

---

# 1. `AI-Chatbot`

## Назначение и режим работы

Простой монолитный **AI Chatbot Assistant** на FastAPI. Пользователь регистрируется, входит в систему и отправляет запрос одной LLM через GitHub Models API.

Основной сценарий: один запрос пользователя → один ответ одной модели. История чата не сохраняется и не передаётся модели. Это не RAG, не агентная платформа и не мультиагентное приложение.

## Архитектура и поток запроса

Слои:

```text
Jinja2 + Vanilla JS
        ↓
FastAPI routes
        ↓
services/chat.py и user_manager.py
        ↓
SQLite / SQLAlchemy или GitHub Models API
```

Для чата:

1. `app/templates/index.html` отправляет `POST /api/chat` с `{ "prompt": "..." }`.
2. `ChatRequest` валидирует тело запроса.
3. `current_user` проверяет JWT в cookie `fastapiusersauth`.
4. `app/api/v1/chat.py` вызывает `get_chat_response()` из `app/services/chat.py`.
5. `AsyncOpenAI` вызывает `chat.completions.create(...)`.
6. В клиент возвращается `{ "response": "..." }`.

Streaming, SSE и WebSocket отсутствуют. Асинхронность `fetch` и typing indicator не являются потоковой генерацией токенов.

## API и auth

Основные маршруты:

- `GET /` — landing page;
- `GET /login` — страница входа;
- `POST /auth/register` — регистрация;
- `POST /auth/login` — вход через cookie;
- `POST /auth/logout` — выход;
- `GET /chat` — защищённая страница чата;
- `POST /api/chat` — запрос к LLM;
- `GET /users/me`, `PATCH /users/me` — профиль;
- `GET /docs` — Swagger UI;
- `GET /health` — health check, также требующий auth.

Используются FastAPI-Users, Cookie backend и JWT/Bearer backend. Хранилище — SQLite по умолчанию (`./sqlite.db`), SQLAlchemy 2.0 async, `aiosqlite`, Alembic.

## Провайдер и модели

Фактически подключена одна конфигурация:

- провайдер: GitHub Models API;
- endpoint: `https://models.github.ai/inference/`;
- модель: `openai/gpt-4o`;
- SDK: `openai`, клиент `AsyncOpenAI`;
- token: `GITHUB_TOKEN`;
- вызов: `client.chat.completions.create`.

`model` и `base_url` описаны как захардкоженные в `app/services/chat.py`. Выбор модели, timeout, `temperature` и `max_tokens` не вынесены в полноценную конфигурацию. OpenAI-compatible endpoints, Ollama и vLLM рассматриваются как направления расширения, а не как фактически подключённые провайдеры.

## Важные пути

Описанная структура исходников:

- `AI-Chatbot/app/main.py` — приложение и маршруты;
- `AI-Chatbot/app/api/v1/chat.py` — chat API;
- `AI-Chatbot/app/api/v1/users.py` — user API;
- `AI-Chatbot/app/services/chat.py` — вызов LLM;
- `AI-Chatbot/app/services/user_manager.py` — управление пользователями;
- `AI-Chatbot/app/core/config.py` — конфигурация;
- `AI-Chatbot/app/db/base.py`, `session.py` — БД;
- `AI-Chatbot/app/models/users.py` — модель пользователя;
- `AI-Chatbot/app/schemas/chat.py`, `users.py` — DTO;
- `AI-Chatbot/app/templates/index.html` — chat UI;
- `AI-Chatbot/alembic/versions/5770fda647a5_create_tables.py` — миграция;
- `AI-Chatbot/pyproject.toml` — зависимости и инструменты.

## Ограничения

- нет истории диалогов;
- нет streaming/SSE/WebSocket;
- нет rate limiting и полноценной обработки ошибок LLM;
- нет автоматических тестов и CI/CD;
- `app/static/` описан как отсутствующий, хотя `main.py` монтирует его;
- есть XSS-риск из-за вставки ответа через `innerHTML`;
- системная инструкция и ввод пользователя конкатенируются;
- `SECRET` имеет небезопасный default;
- Tailwind подключается через CDN.

## Подходящие вопросы

Спрашивай здесь о потоке `POST /api/chat`, FastAPI-Users, cookie/JWT, SQLite и Alembic, добавлении маршрутов и страниц, замене GitHub Models, добавлении истории, исправлении XSS, обработке ошибок, SSE и подготовке MVP к production.

Источники: `AI-Chatbot/01_project_structure.md`, `02_architecture.md`, `03_execution_flow.md`, `08_ai_application_report.md`, `10_models_and_providers.md`, `README.ru.md`.

---

# 2. `GroqStreamChain`

## Назначение и режим работы

Небольшой монолитный чат в реальном времени. FastAPI принимает постоянное WebSocket-соединение, отправляет историю текущей сессии в Groq Cloud API и возвращает ответ потоковыми чанками.

История хранится в обычных in-memory `dict` и теряется при перезапуске процесса. Проект ориентирован на демонстрацию низкой воспринимаемой задержки, а не на production-масштабирование.

## Архитектура и поток запроса

Слои:

- frontend: `templates/index.html`, `static/css/style.css`, `static/js/main.js`;
- transport: `server.py`, HTTP, WebSocket и `ConnectionManager`;
- AI-логика: `services/llm_service.py`;
- модели: `models/chat.py`;
- состояние: in-memory словари в `server.py`.

Поток:

1. `GET /` отдаёт страницу.
2. Браузер подключается к `WS /ws/chat`.
3. Сервер создаёт UUID сессии и отправляет `session_id` и `initial_message`.
4. Клиент отправляет `{ "message": "..." }`.
5. Сервер добавляет сообщение в историю и отправляет `message_received`.
6. `LLMService.generate_response_stream()` добавляет system prompt и вызывает Groq с `stream=True`.
7. Чанки отправляются как `{ "type": "stream", "content": "..." }`.
8. Полный ответ добавляется в историю, затем отправляется `stream_end`.

Синхронный Groq-вызов обёрнут в `asyncio.to_thread`.

## Провайдер и модели

Фактический runtime использует native Groq SDK `groq` и `Groq(api_key=GROQ_API_KEY)`. Основные настройки — `GROQ_API_KEY`, `MODEL_NAME`, `temperature`, `max_tokens`, `top_p`, `stop`.

Документация приводит примеры моделей:

- `llama-3.1-8b-instant`;
- `llama-3.3-70b-versatile`;
- `openai/gpt-oss-120b`;
- `openai/gpt-oss-20b`;
- `groq/compound`;
- `groq/compound-mini`.

`ChatGroq` и LangChain присутствуют как зависимость/задел, но основной runtime-стриминг выполняется не через LangChain, а через native Groq SDK.

## Важные пути и протокол

- `GroqStreamChain/server.py` — FastAPI, `WS /ws/chat`, сессии;
- `GroqStreamChain/config.py` — environment и параметры LLM;
- `GroqStreamChain/system_prompts.py` — системный промпт;
- `GroqStreamChain/models/chat.py` — `Message`, `ChatSession`, `ChatRequest`;
- `GroqStreamChain/services/llm_service.py` — Groq client и generator;
- `GroqStreamChain/templates/index.html` — интерфейс;
- `GroqStreamChain/static/js/main.js` — WebSocket, reconnect и чанки;
- `GroqStreamChain/static/css/style.css` — стили;
- `GroqStreamChain/test_groq.py` — ручная проверка API, не pytest;
- `GroqStreamChain/requirements.txt`, `pyproject.toml` — зависимости.

Типы сообщений server → client: `session_id`, `initial_message`, `message_received`, `stream`, `stream_end`, `error`.

## Ограничения

- нет auth, rate limiting и постоянного хранения;
- нет RAG, tools, function calling и multi-agent orchestration;
- system prompt мутирует историю при каждом запросе и может дублироваться;
- отключённые сессии остаются в `chat_sessions`, что создаёт утечку памяти;
- frontend использует `innerHTML`, возможен XSS;
- нет retry, graceful shutdown, лимитов размера сообщения и полноценной валидации env;
- `asyncio.to_thread` ограничивает масштабирование thread pool;
- в документации расходятся требования Python 3.9+, 3.12+ и 3.13.

## Подходящие вопросы

Спрашивай о WebSocket-жизненном цикле, формате stream-событий, `LLMService`, выборе `MODEL_NAME`, reconnect с exponential backoff, переходе на `AsyncGroq`, Redis, auth, безопасном Markdown-рендеринге и исправлении мутации system prompt.

Источники: `GroqStreamChain/01_project_structure.md`, `02_architecture.md`, `03_execution_flow.md`, `06_frontend_report.md`, `07_ai_models_report.md`, `README.md`, `README_RU.md`.

---

# 3. `llm-council-karpathy`

## Назначение и режим работы

Минималистичный веб-прототип **LLM Council**. Один вопрос проходит через три стадии:

1. **Stage 1** — несколько моделей параллельно дают независимые ответы.
2. **Stage 2** — модели получают ответы под анонимными метками `Response A`, `Response B` и т. п., рецензируют и ранжируют их.
3. **Stage 3** — chairman model синтезирует финальный ответ из исходных ответов и рецензий.

Главная особенность — анонимное взаимное ранжирование. Это не обычный single-model чат и не полноценная агентная платформа с tools, памятью и итеративным планированием.

## Архитектура и поток запроса

```text
frontend/App.jsx
    ↓ HTTP + SSE
backend/main.py
    ↓
backend/council.py
    ├── backend/openrouter.py
    └── backend/storage.py
```

Основной endpoint: `POST /api/conversations/{conversation_id}/message/stream`.

Поток:

1. React делает optimistic update.
2. Backend сохраняет вопрос в JSON и открывает `StreamingResponse`.
3. Stage 1 вызывает `COUNCIL_MODELS` через `asyncio.gather`.
4. Stage 2 анонимизирует ответы, запускает параллельные рецензии и парсит `FINAL RANKING:`.
5. `calculate_aggregate_rankings()` считает средние позиции и `Street Cred`.
6. Stage 3 один раз вызывает `CHAIRMAN_MODEL`.
7. Результат сохраняется в `data/conversations/{id}.json`.
8. Frontend обрабатывает SSE-события и показывает стадии.

SSE-события: `stage1_start`, `stage1_complete`, `stage2_start`, `stage2_complete`, `stage3_start`, `stage3_complete`, `title_complete`, `complete`, `error`.

## Провайдер и модели

Единственный внешний API — OpenRouter: `https://openrouter.ai/api/v1/chat/completions`, авторизация через `OPENROUTER_API_KEY`.

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

Для заголовков используется `google/gemini-2.5-flash`. Состав совета и chairman настраиваются в `backend/config.py`, а модель заголовков описана как захардкоженная в `backend/council.py`. Актуальность model ID нужно проверять отдельно: список провайдера меняется.

## Важные пути

- `llm-council-karpathy/backend/main.py` — FastAPI, CORS, SSE и маршруты;
- `llm-council-karpathy/backend/config.py` — модели и OpenRouter config;
- `llm-council-karpathy/backend/openrouter.py` — запросы к моделям;
- `llm-council-karpathy/backend/council.py` — три стадии, промпты, ranking и aggregation;
- `llm-council-karpathy/backend/storage.py` — JSON CRUD;
- `llm-council-karpathy/frontend/src/App.jsx` — состояние и SSE;
- `llm-council-karpathy/frontend/src/api.js` — ручной SSE parser;
- `llm-council-karpathy/frontend/src/components/Stage1.jsx` — ответы моделей;
- `llm-council-karpathy/frontend/src/components/Stage2.jsx` — рецензии и `Street Cred`;
- `llm-council-karpathy/frontend/src/components/Stage3.jsx` — chairman answer;
- `llm-council-karpathy/data/conversations/` — JSON-разговоры.

В текущем checkout эти исходные каталоги могут отсутствовать и быть представлены только в аналитической документации.

## Ограничения

- нет auth, БД, брокеров, tools, web search и function calling;
- нет настоящего token streaming от LLM;
- UI фактически ограничивает мультитурн-режим, хотя backend хранит несколько сообщений;
- `label_to_model` и aggregate rankings не сохраняются полностью, поэтому после reload теряются детали;
- ручной SSE parser хрупок;
- JSON записывается неатомарно и без блокировок;
- `conversation_id` используется в пути файла и требует защиты от path traversal;
- нет автоматизированных тестов либо часть упомянутых тестов отсутствует.

## Подходящие вопросы

Спрашивай о трёх стадиях council, анонимизации, `FINAL RANKING:`, `Street Cred`, SSE-протоколе, смене состава моделей, JSON-хранилище, переходе к мультитурн-режиму, добавлении retry и сравнении council с multi-agent архитектурой.

Источники: `llm-council-karpathy/01_project_structure.md`, `02_architecture.md`, `03_execution_flow.md`, `06_frontend_report.md`, `07_ai_report.md`, `README.ru.md`.

---

# 4. `openai-responses-python-quickstart`

## Назначение и режим работы

Локальный starter-проект на FastAPI поверх **OpenAI Responses API**. Сервер выступает proxy/orchestrator между браузером и OpenAI. Используются Jinja2, HTMX и SSE; отдельной БД, Redis и брокеров нет.

Возможности включают потоковый чат, Markdown, изображения, голосовой ввод, файлы, Conversations API и инструменты: `code_interpreter`, `file_search`, custom Python functions, MCP, web search и computer use через Playwright.

README отдельно утверждает, что image generation пока не поддерживается, хотя конфигурация и части обработки `imageOutput` уже описаны в коде/документации. Это нужно считать расхождением, а не безусловно готовой функцией.

## Архитектура и поток запроса

```text
Browser: HTMX + sse.js + stream-md.js
        ↓
routers/chat.py, files.py, setup.py, audio.py
        ↓
utils/*
        ↓
OpenAI SDK / Playwright / MCP servers
```

Отправка:

1. `POST /chat/{conversation_id}/send` принимает multipart-форму.
2. Изображения загружаются через Files API.
3. Сообщение сохраняется через `conversations.items.create`.
4. Сервер возвращает HTML-фрагменты, которые вставляет HTMX.
5. Открывается SSE на `GET /chat/{conversation_id}/receive`.

Streaming:

1. Сервер перечитывает `.env` и `tool.config.json`.
2. Собирает `tools[]` согласно `ENABLED_TOOLS`.
3. Вызывает `client.responses.create(..., stream=True)`.
4. `iterate_stream()` преобразует события Responses API в собственные SSE-события.
5. После tool calls результаты записываются в Conversation API и запускается следующий Responses cycle.

Custom function calls могут выполняться параллельно через `asyncio.gather`; computer use выполняется последовательно. MCP может остановить поток до `POST /chat/{conversation_id}/approve`.

## Провайдер и модели

Провайдер только один — OpenAI. Основные API: Responses, Conversations, Items, Files, Vector Stores, Containers и Audio Transcriptions.

Модель хранится в `.env` как `RESPONSES_MODEL`, default в документации — `gpt-5-mini`. В `routers/setup.py` перечислены примеры `gpt-4.1`, `gpt-4o`, `o1`, `o3`, `o4-mini`, `gpt-5`, `gpt-oss-120b` и другие. Для аудио жёстко используется `whisper-1`.

Прямой поддержки Anthropic, Google и локальных моделей нет. Расширение потребует замены `AsyncOpenAI` и адаптации state machine `iterate_stream()`.

## Важные пути

Backend:

- `openai-responses-python-quickstart/main.py` — FastAPI app, lifespan и routers;
- `routers/chat.py` — `/send`, `/receive`, `/approve`, SSE state machine, tools;
- `routers/files.py` — upload/list/delete, Vector Store и downloads;
- `routers/setup.py` — модель, инструкции, tools, MCP и настройки;
- `routers/audio.py` — Whisper;
- `utils/config.py` — Pydantic config, `.env`, `tool.config.json`;
- `utils/function_calling.py`, `function_definitions.py` — registry и JSON Schema;
- `utils/computer_use.py` — Playwright sessions;
- `utils/files.py` — files/vector store;
- `utils/conversations.py` — OpenAI conversation;
- `utils/sse.py` — SSE formatting;
- `utils/custom_functions.py` — пример `get_weather`.

Frontend:

- `templates/layout.html`, `index.html`, `setup.html`;
- `templates/components/assistant-run.html`;
- `templates/components/assistant-step.html`;
- `templates/components/mcp-approval-request.html`;
- `static/stream-md.js` — SSE и инкрементальный Markdown;
- `static/audio-recorder.js` — MediaRecorder и transcription;
- `static/styles.css`.

## Ограничения и безопасность

- нет auth и межпользовательского состояния;
- `utils/files.py` имеет path traversal-риск;
- возможен IDOR через file endpoints;
- API key хранится в `.env`;
- есть риск гонки из-за мутации общего `client.base_url` при container download;
- нет SSE heartbeat и TTL для Playwright sessions;
- `.env` записывается небезопасно при параллельных изменениях;
- `routers/chat.py` слишком монолитен;
- `utils/threads.py` и `ResponseStreamState` описаны как legacy/неиспользуемые.

Нер-live проверки рекомендуется запускать с маркером `-m "not live"`; live-тесты требуют реального `OPENAI_API_KEY`.

## Подходящие вопросы

Спрашивай о Responses stream events, `iterate_stream()`, custom functions и JSON Schema, MCP approval, file search/vector stores, computer use, Playwright, audio, OOB swaps, `DOMPurify`, добавлении SSE events и безопасном исправлении файловых endpoints.

Источники: `openai-responses-python-quickstart/01_project_structure.md`, `02_architecture.md`, `03_execution_flow.md`, `06_frontend_report.md`, `07_ai_models_report.md`, `README.ru.md`.

---

# 5. `Quorum`

## Назначение и режим работы

**NoOversight / Quorum** — платформа координации нескольких LLM-агентов. Пользователь передаёт задачу main agent, который может:

- ответить самостоятельно в Solo-режиме;
- сформировать план делегирования;
- создать специализированных суб-агентов;
- провести несколько раундов обсуждения;
- синтезировать единый ответ.

Документация называет проект production-ready, но аудит фиксирует существенные ограничения. Не следует автоматически считать его готовым к публичному production-деплою.

## Архитектура и поток запроса

Это слоистый асинхронный монолит в одном Uvicorn-процессе:

- React SPA на Vite;
- FastAPI routes, WebSocket и SSE;
- `TaskOrchestrator`, `AgentFactory`, `BaseAgent`, `SettingsService`, `ToolRegistry`;
- PostgreSQL/SQLAlchemy, token tracking, structlog, vector search.

Основной поток:

1. React подключается к `WS /` и отправляет `task` с `message`, `enableCollaboration`, `maxSubAgents`.
2. Backend валидирует Pydantic-модель и сохраняет сообщение через `ConversationService`.
3. `TaskOrchestrator.process_task()` создаёт main agent и отправляет `init`/`agent_status`.
4. При collaboration main agent строит JSON-план делегирования.
5. `AgentFactory` создаёт суб-агентов.
6. Проводится до трёх раундов конференции.
7. Суб-агенты отправляют `agent_message_chunk`.
8. Main agent получает контекст конференции и стримит финальный ответ через `stream`.
9. Отправляется `complete`, а сообщения сохраняются.
10. Frontend обрабатывает события через `streamSlice`.

Fallback transport: `POST /api/task/stream`. Несмотря на заявленную возможность параллельной работы, актуальный WebSocket flow выполняет суб-агентов последовательно; `_execute_sub_agents()` с `asyncio.gather` не является используемым путём.

## Провайдер, модели и инфраструктура

LLM проходят через OpenRouter. В актуальном `AgentFactory.MODEL_MAP` документированы:

- main agent: `anthropic/claude-3.5-sonnet`;
- sub-agent: `anthropic/claude-3-5-haiku`;
- sub-agent: `openai/gpt-4o`.

Другие Gemini/Grok-модели встречаются в списках, но не обязательно выбираются текущим orchestrator. В документации расходятся маркетинговые имена `AgentType`, технические OpenRouter ID и aliases delegation prompt — при работе проверяй конкретную карту моделей.

Инфраструктура:

- PostgreSQL 13+;
- `pgvector` и OpenAI Embeddings `text-embedding-3-small`;
- Redis заявлен как optional, но активный путь в основном описании не подтверждён;
- WebSocket и SSE;
- search providers DuckDuckGo, Tavily, SerpAPI;
- React, TypeScript, Vite, Zustand, Tailwind, Framer Motion.

## Tools и vector search

Есть `BaseTool`, `ToolRegistry` и `WebSearchTool`. Схемы tools передаются модели, но автоматический цикл `LLM → tool call → execute → tool result → LLM` не реализован в текущем streaming flow.

`VectorService` и `EmbeddingRepository` описаны, но embeddings не создаются автоматически при сохранении сообщений в актуальном request flow. Это не следует выдавать за полноценно работающий RAG.

## Важные пути

Backend:

- `Quorum/backend/src/app.py` — FastAPI, lifespan и middleware;
- `backend/src/core/config.py`, `models.py`, `token_models.py`;
- `backend/src/core/orchestrator/task_orchestrator.py` — orchestration;
- `backend/src/agents/base_agent.py`, `agent_factory.py`;
- `backend/src/api/routes/websocket.py` — основной WebSocket;
- `backend/src/api/routes/tasks.py`, `conversations.py`, `settings.py`, `tokens.py`;
- `backend/src/infrastructure/database/` — models, repositories, services, vector service;
- `backend/src/infrastructure/websocket/manager.py`;
- `backend/src/tools/` — tools;
- `backend/tests/` — backend tests.

Frontend:

- `frontend/src/App.tsx`;
- `frontend/src/services/websocket.ts`, `api.ts`;
- `frontend/src/store/slices/streamSlice.ts`;
- `messagesSlice.ts`, `agentsSlice.ts`, `conversationSlice.ts`, `settingsSlice.ts`, `historySlice.ts`;
- `frontend/src/components/AgentPanel.tsx`, `ChatWindow.tsx`, `CostCalculator.tsx`.

## Ограничения

- нет auth и rate limiting, WebSocket не защищён;
- API keys в БД не шифруются;
- token tracking in-memory и теряется после рестарта;
- `/health` может использовать несуществующие поля;
- REST/SSE path имеет другую persistence-логику, чем WebSocket;
- используется `Base.metadata.create_all` вместо полного migration flow;
- суб-агенты последовательны;
- automatic tool calling отсутствует;
- frontend tests отсутствуют;
- README и актуальные routes расходятся;
- в документации расходятся версии Python и список моделей.

## Подходящие вопросы

Спрашивай о `TaskOrchestrator`, делегировании, раундах конференции, WebSocket-событиях, `streamSlice`, добавлении агента или tool, model mapping, settings priority, token/cost analytics, reconnect/cancellation, vector search и безопасной подготовке deployment.

Источники: `Quorum/01_project_structure.md`, `02_architecture.md`, `03_execution_flow.md`, `06_frontend_report.md`, `07_ai_models_report.md`, `08_code_examples.md`, `09_capabilities_multiagent.md`, `README.ru.md`.

---

# 6. `rag-knowledge-base-chatbot`

## Назначение и режим работы

Корпоративный **Support AI Assistant** для ответов по базе знаний. Источники — документы, политики, FAQ, прайс-листы и тикеты WHMCS. Ответы формируются с цитатами и confidence, а при нехватке доказательств система задаёт уточняющий вопрос или эскалирует запрос.

Проект поддерживает многодиалоговый чат, ingestion документов, импорт/краулинг WHMCS, админское одобрение тикетов, настройки LLM, auth, метрики, аудит и debug payload.

Это модульный монолит с enterprise-инфраструктурой, а не LLM Council и не native multi-agent-система: роли LLM связаны через `OrchestratorContext`, а переходы контролирует кодовая state machine.

## Архитектура и RAG-поток

```text
React/Vite SPA
    ↓ HTTP / SSE
FastAPI + middleware
    ↓
API routes → service layer / RAG pipeline
    ↓
OpenSearch + Qdrant + PostgreSQL + Redis + MinIO
```

Основной pipeline:

1. API проверяет guardrails и сохраняет запрос в PostgreSQL.
2. Загружается история диалога.
3. Intent Cache может вернуть готовый ответ без LLM/retrieval.
4. Определяется язык.
5. LLM-нормализатор строит `QuerySpec`.
6. `Orchestrator` проходит `UNDERSTAND → RETRIEVE → ASSESS_EVIDENCE → DECIDE → GENERATE → VERIFY`.
7. `RETRIEVE` параллельно делает BM25 в OpenSearch и vector search в Qdrant, объединяет результаты через RRF и применяет reranker.
8. При слабых доказательствах выполняется targeted retry, обычно до трёх попыток.
9. `DECIDE` выбирает `GENERATE`, `ASK_USER` или `ESCALATE`.
10. `GENERATE` формирует ответ с citations.
11. `VERIFY` выполняет claim-level review, снижает confidence или меняет маршрут при unsupported claims.
12. Ответ сохраняется в `Message`, citations — в `Citation`.

## Ingestion и WHMCS

Ingestion обычно запускается через `POST /v1/admin/ingest` и Celery:

```text
Admin API → Celery → очистка и semantic chunking → checksum/idempotency
→ PostgreSQL → embeddings → Qdrant → OpenSearch
```

SHA-256 предотвращает повторное embedding неизменившегося документа. Старые chunks удаляются при переиндексации; raw content может храниться в MinIO.

`app/crawlers/whmcs.py` использует Playwright. Тикет проходит статусы `pending`, `approved` или `rejected`; одобренные тикеты экспортируются в `source/` и индексируются.

## Провайдеры и AI-роли

Текстовые LLM проходят через `LLMGateway`/`OpenAIGateway` в `app/services/llm_gateway.py`, протокол — асинхронный OpenAI Chat Completions с JSON-контрактами.

Default-модели:

- `gpt-5.2` — generation и self-critic;
- `gpt-4o-mini` — normalization, routing, evidence evaluation и query rewriting;
- `gpt-3.5-turbo` — fallback;
- `text-embedding-3-small` — embeddings, 1536 dimensions;
- `cross-encoder/ms-marco-MiniLM-L-6-v2` — локальный reranker;
- `rerank-multilingual-v3.0` — Cohere reranker.

Через `base_url` возможны OpenAI-compatible endpoints. Model config имеет уровни `environment → app_config в PostgreSQL → Admin API / Settings UI`; модель можно менять без redeploy.

LLM-роли включают Normalizer, Query Rewriter, Evidence Selector/Evaluator, Decision Router, Generator, Self-Critic, Final Polish и другие. Это не независимые агенты с прямым tool calling.

## Важные пути

Backend:

- `rag-knowledge-base-chatbot/app/main.py` — app factory, lifespan, middleware;
- `app/api/routes/` — conversations, reply, documents, tickets, admin, auth, dashboard, health;
- `app/core/` — config, auth, guardrails, WAF, rate limiting, logging, tracing;
- `app/search/` — OpenSearch, Qdrant, embeddings, reranker;
- `app/services/answer_service.py` — вход в RAG;
- `app/services/orchestrator.py` — state machine;
- `app/services/phases/` — retrieval, assess, decide, generate, verify;
- `app/services/retrieval.py` — hybrid retrieval и evidence;
- `app/services/normalizer.py`, `reviewer.py`, `llm_gateway.py`, `model_router.py`;
- `worker/tasks.py` — Celery ingestion;
- `tests/` — backend pipeline tests;
- `scripts/`, `alembic/versions/`, `source/`, `docker-compose.yml`.

Frontend:

- `frontend/src/api/client.ts` — typed API;
- `frontend/src/contexts/AuthContext.tsx` — auth;
- `frontend/src/pages/` — admin screens;
- публичный chat widget находится вне этого репозитория, а frontend здесь в основном является административной SPA.

## Ограничения и production-риски

- крупные модули `retrieval.py`, `normalizer.py`, `reviewer.py`, `admin.py`;
- `OrchestratorContext.extra` нетипизирован;
- нет frontend unit/e2e tests и явного CI в описании;
- Redis connections создаются не через единый pool;
- URL fetch и website crawl требуют SSRF-защиты;
- в Docker Compose OpenSearch security отключён;
- rate limit при недоступном Redis fail-open;
- default `JWT_SECRET` небезопасен;
- часть API выдаёт псевдостриминг: pipeline сначала полностью выполняется, а затем готовый ответ отдаётся кусками по 100 символов;
- для полноценной production-оценки нужно проверить реальный код, миграции и конфигурацию, а не только документацию.

## Подходящие вопросы

Спрашивай о фазах RAG, `ASK_USER`/`ESCALATE`, BM25 + vector + RRF, Qdrant/OpenSearch, reranking, citations, QuerySpec, fallback и cache, ingestion и idempotency, WHMCS approval workflow, JWT/API keys, admin SPA, debug payload, Celery, Docker Compose и security hardening.

Источники: `rag-knowledge-base-chatbot/01_project_structure.md`, `02_architecture.md`, `03_execution_flow.md`, `06_frontend_report.md`, `07_ai_models_report.md`, `08_ai_code_examples.md`, `README.ru.md`.

---

## Правила выбора контекста для ассистента

1. **Сначала определи проект по предмету вопроса.**
   - `GITHUB_TOKEN`, FastAPI-Users, SQLite, `POST /api/chat` → `AI-Chatbot`.
   - `GROQ_API_KEY`, `/ws/chat`, `stream_end`, `MODEL_NAME` → `GroqStreamChain`.
   - `COUNCIL_MODELS`, `CHAIRMAN_MODEL`, `FINAL RANKING`, `Street Cred` → `llm-council-karpathy`.
   - `responses.create`, `iterate_stream`, MCP approval, `computer_use`, Vector Store → `openai-responses-python-quickstart`.
   - `TaskOrchestrator`, `AgentFactory`, `agent_message_chunk`, `enableCollaboration` → `Quorum`.
   - `QuerySpec`, `OrchestratorContext`, `OpenSearch`, `Qdrant`, `Citation`, `WHMCS` → `rag-knowledge-base-chatbot`.
2. **Если вопрос сравнительный, используй разделы всех затронутых проектов.** Не переносить свойства одного проекта на другой: например, WebSocket есть у `GroqStreamChain` и `Quorum`, но не является основным транспортом `rag-knowledge-base-chatbot`.
3. **После выбора проекта сначала читай его профиль, затем первичные документы, затем конкретный исходный файл.** Для архитектурных вопросов начинать с `01_project_structure.md` и `02_architecture.md`; для runtime — с `03_execution_flow.md`; для моделей — с отчёта `07_*` или `10_models_and_providers.md`.
4. **Не выдавай roadmap за готовую функциональность.** Особенно внимательно проверяй tools в `Quorum`, image generation в OpenAI quickstart, vector search в `Quorum` и заявленную production-ready характеристику.
5. **Проверяй актуальность model ID и API.** Названия моделей и доступность endpoints могут меняться. В ответе разделяй «указано в документации» и «подтверждено текущим исходным кодом».
6. **При изменениях кода сначала проверь существование описанного пути.** В текущем checkout многие исходные каталоги представлены только описанием; нельзя придумывать отсутствующие файлы или считать документацию доказательством запуска.
7. **Учитывай известные риски.** Не заявляй production-readiness без оговорок, не раскрывай секреты из `.env`, не ослабляй auth/validation и не игнорируй XSS, path traversal, SSRF, IDOR, race condition и отсутствие rate limiting.
8. **Для задач по коду применяй минимальные изменения.** Перед правкой прочитай конкретный файл, после правки проверь соответствующие тесты, линтеры или хотя бы синтаксис. Аналитические документы не редактируй без отдельного запроса.
9. **При неоднозначном вопросе попроси уточнить проект**, если по ключевым словам нельзя надёжно определить, идёт ли речь о простом чате, council, multi-agent или RAG.

## Общие замечания о документации

- В русскоязычных `README`, `AGENTS` и `CLAUDE` иногда указаны английские имена файлов и каталог `docs/`, которых нет в текущем checkout.
- Версии Python и зависимости местами противоречат друг другу; для запуска приоритет имеют реальные manifest/lock-файлы, если они доступны.
- Списки моделей и provider capabilities могут быть устаревшими.
- `Quorum` и `rag-knowledge-base-chatbot` имеют наиболее широкие описания, но их аудиты явно отмечают неполностью подключённые функции.
- Если утверждение нельзя подтвердить текущим файлом или несколькими согласованными документами, формулируй его как «описано в документации», а не как гарантированную работающую возможность.
