# AGENTS.md — Сводный навигатор по 6 проектам AI-чатов

> Этот файл — единая точка входа для AI-ассистентов (харнесов). Здесь описано, **какой проект где
> лежит, что делает, на чём построен и какие LLM/провайдеры использует**. Прежде чем погружаться
> в код конкретного проекта, читайте соответствующую папку `docs/` внутри него — это единый
> источник истины, избавляющий от слепого обхода репозитория.

## Как пользоваться этим файлом

1. По вопросу пользователя определите, к какому проекту (или проектам) он относится.
2. Откройте нужную папку (см. карту ниже) и прочитайте её `README*.md` + файлы `NN_*.md` из `docs/`.
3. Каждый проект также содержит собственный `AGENTS*.md` / `CLAUDE*.md` с детальными инструкциями.
4. Документация во всех проектах построена по единому шаблону (нумерованные файлы), поэтому
   нужный раздел легко найти по имени:
   - `01_project_structure.md` — карта проекта, дерево каталогов, ответственность модулей
   - `02_architecture.md` — архитектура, паттерны, поток данных, конфигурация
   - `03_execution_flow.md` — жизненный цикл, бизнес-процессы, роутинг, обработка ошибок
   - `04_code_quality.md` — техдолг, code smells, безопасность, узкие места
   - `05_optimization_roadmap.md` — приоритизированный план рефакторинга (P0–P3)
   - `06_*report.md` — отчёт по фронтенду
   - `07_*report.md` — отчёт по интеграции с AI-моделями (модели, провайдеры, формат общения)
   - `08+` — дополнительные материалы (примеры кода, возможности, модели и т.д.)

---

## Карта проектов

| # | Папка | Название | Тип чата | LLM-провайдер | Стек бэкенда | Стек фронтенда |
|---|-------|----------|----------|---------------|--------------|----------------|
| 1 | `AI-Chatbot/` | AI Chatbot Assistant | Одиночный AI-чат с авторизацией | GitHub Models (GPT-4o, OpenAI-compatible) | FastAPI, SQLAlchemy 2.0, SQLite, FastAPI-Users (JWT) | Jinja2 + Tailwind CSS (glassmorphism) |
| 2 | `GroqStreamChain/` | GroqStreamChain | Real-time стриминговый чат (WebSocket) | Groq Cloud (нативный Groq SDK) | FastAPI, WebSocket | Vanilla JS + HTML/CSS |
| 3 | `llm-council-karpathy/` | LLM Council | «Совет LLM»: мульти-модель + рецензирование + синтез | OpenRouter (несколько моделей: GPT, Gemini, Claude, Grok) | FastAPI, async httpx | React + Vite |
| 4 | `openai-responses-python-quickstart/` | OpenAI Responses Quickstart | Шаблон чата на Responses API с инструментами | OpenAI (эксклюзивно) | FastAPI, OpenAI SDK 2.0 | Jinja2 + HTMX |
| 5 | `Quorum/` | NoOversight (Quorum) | Мульти-агентная платформа с оркестратором | OpenRouter через LangChain (Claude, GPT, Gemini) | FastAPI, PostgreSQL, LangChain | React 18 + TypeScript + Zustand |
| 6 | `rag-knowledge-base-chatbot/` | Auto Reply Chatbot / Support AI | Enterprise RAG-чатбот поддержки | OpenAI + любой OpenAI-compatible (мульти-ролевой пайплайн) | FastAPI, PostgreSQL, Redis, Celery, OpenSearch, Qdrant | React 19 + Vite |

---

## Детальное описание каждого проекта

### 1. AI-Chatbot — `AI-Chatbot/`

**Что это:** Полнофункциональное веб-приложение — AI-чат-бот с регистрацией/логином, защищёнными
маршрутами и чатом в реальном времени. Бесплатный AI-инференс через GitHub Models.

**Ключевое:**
- **Провайдер LLM:** GitHub Models API (`https://models.github.ai/inference/`), OpenAI-compatible
  Chat Completions. Модель: `openai/gpt-4o`. Клиент: `AsyncOpenAI` с кастомным `base_url`.
- **Авторизация:** JWT + Cookie через FastAPI-Users.
- **БД:** SQLite (`aiosqlite`), миграции Alembic. Легко меняется на PostgreSQL.
- **Фронтенд:** серверный рендеринг Jinja2, Tailwind CSS (CDN), glassmorphism-дизайн, ванильный JS.
- **Секрет:** `GITHUB_TOKEN` (Personal Access Token с правом `models:read`).

**Где что искать:**
- `app/services/chat.py` — LLM-клиент (вызов GitHub Models)
- `app/api/v1/` — роутеры (chat, users)
- `app/core/config.py` — настройки (Pydantic Settings)
- `docs/10_models_and_providers.md` — детальный разбор моделей и провайдеров

**Документация:** `AI-Chatbot/README.ru.md`, `AI-Chatbot/AGENTS.ru.md`, файлы `01`–`10` в папке.

---

### 2. GroqStreamChain — `GroqStreamChain/`

**Что это:** Приложение чата в реальном времени с потоковой передачей ответов от ИИ. Общение
клиента с сервером — через WebSocket, стриминг токенов от LLM — через Groq.

**Ключевое:**
- **Провайдер LLM:** Groq Cloud API (`api.groq.com`), нативный `groq` SDK. Модель задаётся
  через `MODEL_NAME` в `.env` (по умолчанию `llama-3.1-8b-instant`). Провайдер жёстко зашит.
- **Транспорт:** WebSocket (`WS /ws/chat`), JSON-фреймы. Стриминг чанков: `{"type":"stream",...}`.
- **Сессии:** UUID-based, in-memory (`models/chat.py` — `ChatSession`, `Message`).
- **Фронтенд:** статические HTML/CSS/JS, адаптивная вёрстка, мобильная версия.
- **Секрет:** `GROQ_API_KEY`.

**Где что искать:**
- `services/llm_service.py` — интеграция с Groq (потоковая передача)
- `server.py` — FastAPI-приложение, WebSocket-эндпоинт
- `config.py` — конфигурация (HOST, PORT, GROQ_API_KEY, MODEL_NAME)
- `system_prompts.py` — шаблоны системных промптов

**Документация:** `GroqStreamChain/README_RU.md`, `GroqStreamChain/AGENTS_RU.md`, файлы `01`–`07`.

---

### 3. LLM Council — `llm-council-karpathy/`

**Что это:** Локальное веб-приложение «совет из LLM» (идея Andrej Karpathy). Один запрос
пользователя отправляется нескольким LLM параллельно, затем они анонимно рецензируют и
ранжируют ответы друг друга, а модель-«председатель» синтезирует финальный ответ.

**Три стадии:**
1. **Первые мнения** — все модели совета отвечают на вопрос (параллельно).
2. **Рецензирование** — модели ранжируют анонимные ответы друг друга (без знания, чей ответ).
3. **Финальный ответ** — «Председатель» компилирует единый ответ из всех мнений.

**Ключевое:**
- **Провайдер LLM:** OpenRouter API (единый шлюз к OpenAI, Anthropic, Google, xAI и др.).
  Один ключ `OPENROUTER_API_KEY`.
- **Модели совета:** настраиваются в `backend/config.py` (`COUNCIL_MODELS`), например
  GPT-5.1, Gemini 3 Pro, Claude Sonnet 4.5, Grok 4. `CHAIRMAN_MODEL` — модель-председатель.
- **Транспорт:** REST + SSE-стриминг. Асинхронные параллельные вызовы через `httpx`.
- **Хранилище:** JSON-файлы в `data/conversations/`.
- **Фронтенд:** React + Vite, react-markdown.

**Где что искать:**
- `backend/council.py` — оркестрация 3 стадий, промпты, парсинг рейтингов
- `backend/openrouter.py` — единственный HTTP-клиент к LLM (`query_model`, `query_models_parallel`)
- `backend/config.py` — список моделей совета и председателя
- `backend/main.py` — FastAPI-роуты, SSE

**Документация:** `llm-council-karpathy/README.ru.md`, `llm-council-karpathy/AGENTS.ru.md`, файлы `01`–`07`.

---

### 4. openai-responses-python-quickstart — `openai-responses-python-quickstart/`

**Что это:** Шаблон быстрого старта чат-приложения на базе OpenAI **Responses API** (преемник
устаревшего Assistants API). Сервер — тонкий посредник между браузером и OpenAI. Состояние
диалога хранится на стороне OpenAI (Conversation API).

**Ключевое:**
- **Провайдер LLM:** OpenAI (эксклюзивно). SDK `openai>=2.0.0`, класс `AsyncOpenAI`.
- **API:** Responses API (`responses.create`), Conversations API, Files API, Vector Store,
  audio transcriptions (Whisper).
- **7 типов инструментов:** Code Interpreter, File Search, Custom Functions, MCP, Web Search,
  Computer Use (Playwright headless-браузер), Image Generation.
- **Возможности:** SSE-стриминг с инкрементальным Markdown, мультимодальный ввод (vision),
  голосовой ввод (аудио → Whisper), MCP-интеграция с approval-флоу.
- **Конфигурация:** модель, инструкции, инструменты настраиваются через веб-UI `/setup`,
  хранятся в `.env` + `tool.config.json` (без перезапуска).
- **Фронтенд:** Jinja2 + HTMX, `marked` + `DOMPurify` для Markdown.
- **Секрет:** `OPENAI_API_KEY`.

**Где что искать:**
- `routers/chat.py` — основной чат-роутер, стриминг, вызовы Responses API
- `routers/setup.py` — настройка ассистента, список моделей
- `utils/conversations.py` — управление состоянием диалога
- `utils/computer_use.py` — Computer Use (Playwright)
- `utils/custom_functions.py` — пример пользовательской функции

**Документация:** `openai-responses-python-quickstart/README.ru.md`, файлы `01`–`07`.

---

### 5. Quorum (NoOversight) — `Quorum/`

**Что это:** Production-ready мульти-агентная AI-платформа. Несколько AI-агентов (Claude, GPT,
Gemini) коллаборируют над сложными задачами через единый API OpenRouter. Интеллектуальный
оркестратор делегирует подзадачи специализированным агентам и синтезирует их ответы.

**Ключевое:**
- **Провайдер LLM:** OpenRouter (OpenAI-compatible), один ключ `OPENROUTER_API_KEY` → доступ
  к Anthropic, OpenAI, Google, X.AI и сотням моделей.
- **LLM-слой:** `langchain-openai.ChatOpenAI` с `base_url` на OpenRouter. Асинхронно:
  `ainvoke` / `astream`.
- **Архитектура агентов:** `BaseAgent` (главный) + `N` sub-агентов. `TaskOrchestrator`
  решает, кому делегировать, проводит раунды обсуждения, синтезирует результат.
- **Трекинг токенов:** `TokenTrackingCallback` (LangChain callback) — стоимость по прайсингу
  9 моделей, in-memory агрегация по сессиям/агентам.
- **Транспорт:** WebSocket + SSE для real-time стриминга.
- **БД:** PostgreSQL (диалоги), Alembic-миграции.
- **Фронтенд:** React 18 + TypeScript, Tailwind CSS, Zustand, Framer Motion.
- **Инструменты:** система инструментов с web search, расширяемая через `BaseTool` + реестр.

**Где что искать:**
- `backend/src/agents/base_agent.py` — обёртка над ChatOpenAI (стриминг, история, tools)
- `backend/src/agents/agent_factory.py` — маппинг AgentType → модель, system prompts
- `backend/src/core/orchestrator/task_orchestrator.py` — мульти-агентная координация
- `backend/src/infrastructure/tracking/` — трекинг токенов и стоимости
- `backend/src/tools/` — реализация инструментов + реестр

**Документация:** `Quorum/README.ru.md`, `Quorum/AGENTS.ru.md`, файлы `01`–`09`.

---

### 6. rag-knowledge-base-chatbot — `rag-knowledge-base-chatbot/`

**Что это:** Enterprise RAG-чатбот (Retrieval-Augmented Generation) для поддержки клиентов.
Отвечает на вопросы через гибридный поиск (BM25 + векторный) по базе знаний. База строится
из веб-краулера (WHMCS-тикеты), вручную подготовленных диалогов и непрерывного обучения на
одобрённых тикетах.

**Ключевое:**
- **Провайдер LLM:** OpenAI + любой OpenAI-compatible endpoint (через `base_url`).
  Модели по умолчанию: primary `gpt-5.2`, economy `gpt-4o-mini`, fallback `gpt-3.5-turbo`.
- **Архитектура LLM:** мульти-ролевой пайплайн — до 8–10 вызовов разных ролей за один запрос
  (нормализатор запроса, оценка доказательств, генерация, самокритика, reasoning prepass и др.).
  Координация — детерминированным оркестратором (не LLM). Вывод каждой роли — строгий JSON.
- **Поиск:** гибридный — OpenSearch (BM25) + Qdrant (векторный) + реранкинг (cross-encoder /
  Cohere / no-op). Эмбеддинги: `text-embedding-3-small` (1536 dims).
- **Источники данных:** краулер WHMCS (Playwright), JSON-файлы (`sample_docs.json`,
  `sample_conversations.json`), импорт SQL-дампов, загрузка по URL, краулинг сайта.
- **Непрерывное обучение:** краулинг → проверка (одобрить/отклонить) → экспорт → ingestion.
- **Инфраструктура:** PostgreSQL 15+, Redis + Celery (очереди ingestion), MinIO/S3 (файлы).
- **Авторизация:** 3 метода — Bearer JWT, X-API-Key (sk_*), X-Admin-API-Key.
- **Фронтенд:** React 19 + Vite 7 + Tailwind CSS (диалоги, документы, краулинг, дашборд,
  настройки, API-токены, справочник API).

**Где что искать:**
- `app/services/llm_gateway.py` — единый абстрактный шлюз к LLM (OpenAIGateway)
- `app/services/normalizer.py` — нормализация запроса (QuerySpec, интенты, retrieval profile)
- `app/services/phases/generate.py` — фаза генерации ответа с evidence
- `app/services/self_critic.py` — самокритика сгенерированного ответа
- `app/search/` — OpenSearch (BM25), Qdrant (векторный), reranker, embeddings
- `app/crawlers/` — краулер WHMCS (Playwright)
- `app/api/routes/` — auth, conversations, reply, tickets, documents, admin, health, dashboard

**Документация:** `rag-knowledge-base-chatbot/README.ru.md`, `rag-knowledge-base-chatbot/AGENTS.ru.md`, файлы `01`–`08`.

---

## Сравнительная таблица: ключевые отличия

| Критерий | AI-Chatbot | GroqStreamChain | LLM Council | OpenAI Responses | Quorum | RAG Chatbot |
|----------|-----------|-----------------|-------------|------------------|--------|-------------|
| **Кол-во моделей** | 1 (GPT-4o) | 1 (на выбор Groq) | 4+ (совет) | 1 (на выбор OpenAI) | N (агенты) | мульти-роль (1 провайдер) |
| **Мультиагентность** | нет | нет | совет моделей | нет | да (оркестратор + sub-agents) | мульти-ролевой пайплайн |
| **RAG / база знаний** | нет | нет | нет | file search (OpenAI) | web search (инструмент) | да (гибридный поиск) |
| **Стриминг** | индикатор набора | WebSocket (токены) | SSE | SSE (Markdown) | WebSocket + SSE | SSE |
| **Авторизация** | JWT (FastAPI-Users) | нет | нет | API key в UI | нет (API-level) | JWT + API-key + Admin-key |
| **БД** | SQLite | in-memory | JSON-файлы | сторона OpenAI | PostgreSQL | PostgreSQL + OpenSearch + Qdrant |
| **Фронтенд** | Jinja2 + Tailwind | Vanilla JS | React + Vite | Jinja2 + HTMX | React + TS + Zustand | React 19 + Vite |
| **Сложность** | низкая | низкая | средняя | средняя | высокая | очень высокая |

---

## Быстрый выбор проекта по вопросу

| Если вопрос про… | Смотрите проект |
|---|---|
| Бесплатный AI через GitHub Models, JWT-авторизация, glassmorphism UI | `AI-Chatbot/` |
| WebSocket-стриминг, Groq SDK, real-time чанк-стриминг | `GroqStreamChain/` |
| Несколько LLM отвечают вместе, рецензирование, ранжирование, «совет» | `llm-council-karpathy/` |
| OpenAI Responses API, инструменты (code/file/web/computer use/MCP), HTMX | `openai-responses-python-quickstart/` |
| Мульти-агентная коллаборация, оркестратор, делегирование sub-agents, трекинг токенов | `Quorum/` |
| RAG, гибридный поиск, база знаний, краулер WHMCS, support-чатбот, непрерывное обучение | `rag-knowledge-base-chatbot/` |

---

## Общие принципы для всех проектов

- **Документация первична:** всегда читайте `docs/` (файлы `NN_*.md`) перед работой с кодом.
  Каждый проект содержит собственный `AGENTS*.md` с инструкциями для AI-харнесов.
- **Единый шаблон документации:** `01_structure → 02_architecture → 03_flow → 04_quality →
  05_roadmap → 06_frontend → 07_ai_models → 08+ extras`.
- **Язык документации:** русские версии — `*.ru.md` / `*_RU.md`; английские — `*.md`.
- **Управление пакетами:** большинство использует `uv` для Python; фронтенды — `npm`.
- **Бэкенд-фреймворк:** во всех 6 проектах — FastAPI (Python 3.10–3.13).
- **Лицензия:** MIT во всех проектах.
