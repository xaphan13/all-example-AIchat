# 01 — Карта проекта (Project Structure)

> Единый источник истины о структуре проекта NoOversight / Quorum.
> Версия анализа: август 2026.

---

## 1. Назначение проекта

**NoOversight (Quorum)** — production-ready платформа для мульти-агентного взаимодействия AI-моделей. Система позволяет нескольким LLM-агентам (Claude, GPT, Gemini и др.) коллаборировать над сложными задачами через единый OpenRouter API. Архитектура — streaming-first, event-driven, с real-time обратной связью через WebSocket и SSE.

Ключевые возможности:
- Интеллектуальный оркестратор делегирует подзадачи специализированным агентам.
- Параллельное выполнение суб-агентов с последующим синтезом ответов.
- Real-time стриминг токенов через WebSocket.
- Персистентность диалогов в PostgreSQL с поддержкой векторного поиска (pgvector).
- Трекинг token usage и расчёт стоимости по моделям.
- Система инструментов (tools) с web search через DuckDuckGo/Tavily/SerpAPI.

---

## 2. Дерево директорий и ключевых файлов

```
Quorum/
├── README.md                          # Основная документация проекта (install, usage, API reference)
├── ARCHITECTURE.md                    # Архитектурный deep-dive (data flow, паттерны, deployment)
├── pyproject.toml                     # Python project config (uv/PEP-621), требует Python >=3.13
├── Makefile                           # Root makefile: install, start, stop, dev, test, lint, build
├── setup.sh                           # Скрипт первичной настройки окружения
│
├── scripts/                           # Shell-скрипты управления сервисами
│   ├── start-backend.sh               # Запуск backend (foreground/background)
│   ├── start-frontend.sh              # Запуск frontend dev server
│   ├── stop-backend.sh                # Остановка backend по PID
│   ├── stop-frontend.sh               # Остановка frontend по PID
│   └── test_websocket.py              # Ручное тестирование WebSocket соединения
│
├── backend/                           # FastAPI backend (Python, async)
│   ├── Makefile                       # Backend-specific make targets (install, dev, test, lint)
│   ├── requirements.txt               # Python-зависимости (fastapi, sqlalchemy, langchain, и др.)
│   ├── pytest.ini                     # pytest config: async mode, coverage, markers
│   ├── .coveragerc                    # Coverage configuration
│   ├── alembic.ini                    # Alembic migration config
│   ├── config/
│   │   └── env_template.txt           # Шаблон .env файла со всеми переменными окружения
│   ├── alembic/                       # Database migrations
│   │   ├── env.py                     # Alembic environment (async engine, autogenerate)
│   │   ├── script.py.mako             # Template для новых миграций
│   │   └── versions/                  # Директория с файлами миграций
│   ├── examples/
│   │   └── web_search_example.py      # Пример использования WebSearchTool
│   ├── tests/                         # Backend test suite
│   │   ├── conftest.py                # Pytest fixtures (app, db, mocks)
│   │   ├── test_app.py                # Тесты FastAPI app (lifespan, routes)
│   │   ├── test_config.py             # Тесты Settings (env vars, defaults)
│   │   ├── test_models.py             # Тесты Pydantic моделей
│   │   ├── test_base_agent.py         # Тесты BaseAgent (streaming, response, tools)
│   │   ├── test_agent_factory.py      # Тесты AgentFactory (model mapping, prompts)
│   │   ├── test_task_orchestrator.py  # Тесты TaskOrchestrator (delegation, synthesis)
│   │   └── test_tools.py              # Тесты tool registry и web_search
│   └── src/                           # Исходный код backend
│       ├── __init__.py
│       ├── app.py                     # Точка входа FastAPI: create_app(), lifespan, middleware, routers
│       │
│       ├── core/                      # Бизнес-логика и конфигурация
│       │   ├── config.py              # Settings (pydantic-settings): API keys, DB, Redis, logging
│       │   ├── models.py              # Pydantic модели: AgentType, Message, TaskRequest, StreamChunk и др.
│       │   ├── token_models.py        # TokenUsage, SessionUsage, ModelPricing, MODEL_PRICING_CONFIG
│       │   ├── settings_service.py    # SettingsService — доступ к настройкам (DB → env fallback)
│       │   └── orchestrator/
│       │       └── task_orchestrator.py  # TaskOrchestrator — ядро мульти-агентной координации
│       │
│       ├── agents/                    # Реализация AI-агентов
│       │   ├── base_agent.py          # BaseAgent: LangChain интеграция, streaming, tools, token tracking
│       │   └── agent_factory.py       # AgentFactory: MODEL_MAP, SYSTEM_PROMPTS, create_main/sub_agent
│       │
│       ├── api/                       # HTTP/WebSocket API слой
│       │   ├── middleware/
│       │   │   └── logging.py         # LoggingMiddleware (correlation ID), PerformanceLoggingMiddleware
│       │   └── routes/
│       │       ├── health.py          # GET /, GET /health — health checks
│       │       ├── tasks.py           # POST /api/task/stream (SSE), POST /api/task, POST /api/reset
│       │       ├── websocket.py       # WS /ws — bidirectional streaming, task processing, cancel
│       │       ├── conversations.py   # CRUD для conversations: list, get, delete, update, by task_id
│       │       ├── settings.py        # GET/PUT /api/settings, GET /api/settings/api-keys/validate
│       │       └── tokens.py          # Token analytics: pricing, calculate, compare, stats, cleanup
│       │
│       ├── infrastructure/            # Инфраструктурный слой
│       │   ├── database/
│       │   │   ├── connection.py      # DatabaseManager: async engine, session factory, get_db dependency
│       │   │   ├── models.py          # SQLAlchemy ORM: Conversation, Message, Embedding (pgvector)
│       │   │   ├── repository.py      # ConversationRepository, MessageRepository, EmbeddingRepository
│       │   │   ├── conversation_service.py  # ConversationService — persistence layer для диалогов
│       │   │   ├── settings_models.py # AppSettings ORM model (singleton settings table)
│       │   │   ├── settings_repository.py  # SettingsRepository — CRUD для AppSettings
│       │   │   ├── vector_service.py  # VectorService — embeddings через OpenAI API, similarity search
│       │   │   ├── init_db.py         # Утилита инициализации БД (create tables, extensions)
│       │   │   └── __init__.py        # Публичный API модуля database
│       │   ├── logging/
│       │   │   └── config.py          # structlog setup: JSON/console, context vars, sensitive data censor
│       │   ├── tracking/
│       │   │   ├── callback_handler.py  # TokenTrackingCallback — LangChain AsyncCallbackHandler
│       │   │   └── token_manager.py   # TokenTrackingManager — сессии, агрегация, аналитика (in-memory)
│       │   └── websocket/
│       │       └── manager.py         # ConnectionManager — WS connections, subscriptions, broadcast
│       │
│       ├── tools/                     # Система инструментов для агентов
│       │   ├── base.py                # BaseTool (ABC), ToolResult, ToolParameter, get_schema()
│       │   ├── registry.py            # ToolRegistry — регистрация, lookup, execute, singleton
│       │   └── web_search.py          # WebSearchTool — DuckDuckGo, Tavily, SerpAPI providers
│       │
│       └── utils/
│           └── cost_calculator.py     # Утилиты расчёта стоимости: compare, cheapest, batch, monthly
│
└── frontend/                          # React 18 + TypeScript SPA
    ├── package.json                   # npm dependencies и scripts
    ├── Makefile                       # Frontend make targets (install, dev, build, lint)
    ├── vite.config.ts                 # Vite config: proxy /api → localhost:8000, alias '@'
    ├── tsconfig.json                  # TypeScript config (strict mode)
    ├── tsconfig.node.json             # TS config для vite.config.ts
    ├── tailwind.config.js             # Tailwind CSS theme и plugins
    ├── postcss.config.js              # PostCSS: tailwindcss + autoprefixer
    ├── index.html                     # HTML entry point
    └── src/
        ├── main.tsx                   # React entry point (ReactDOM.createRoot)
        ├── App.tsx                    # Главный компонент: layout, WS connection, send/stop
        ├── index.css                  # Глобальные стили (Tailwind directives, custom CSS)
        ├── vite-env.d.ts              # Vite environment type declarations
        ├── shaders.d.ts               # Type declarations для GLSL shader imports
        │
        ├── components/                # React компоненты
        │   ├── ChatWindow.tsx         # Отображение ленты сообщений (user + assistant)
        │   ├── ChatInput.tsx          # Поле ввода с auto-resize, кнопка send/stop
        │   ├── MessageBubble.tsx      # Отдельное сообщение с markdown rendering
        │   ├── MarkdownRenderer.tsx   # React-markdown + remark-gfm рендерер
        │   ├── AgentPanel.tsx         # Правая панель: список активных агентов
        │   ├── AgentCard.tsx          # Карточка агента: статус, прогресс, текущая задача
        │   ├── AgentConversation.tsx  # Отображение inter-agent диалога по раундам
        │   ├── AgentToolDisplay.tsx   # Отображение tool usage (web search results)
        │   ├── ChatHistory.tsx        # Левая панель: история диалогов, поиск
        │   ├── Settings.tsx           # Модальное окно настроек (API keys, theme, agents)
        │   ├── QuorumSettings.tsx     # Настройки Quorum-режима (модели, раунды)
        │   ├── ModeSelector.tsx       # Переключатель solo/quorum режима
        │   ├── CostCalculator.tsx     # UI калькулятора стоимости токенов
        │   ├── TokenUsageDisplay.tsx  # Отображение token usage статистики
        │   ├── ToolUsageDisplay.tsx   # Отображение результатов web search
        │   ├── ErrorBoundary.tsx      # React error boundary с fallback UI
        │   ├── GLSLBackground.tsx     # WebGL/GLSL анимированный фон
        │   └── Logo.tsx               # SVG логотип NoOversight
        │
        ├── hooks/                     # Custom React hooks
        │   ├── useWebSocket.ts        # WS lifecycle: connect, sendTask, stopGeneration, handlers
        │   └── useLogger.ts           # Logger hook с auto context и mount tracking
        │
        ├── services/                  # Сервисный слой (API клиенты, logging)
        │   ├── api.ts                 # APIService: SSE streaming, HTTP requests, health check
        │   ├── websocket.ts           # WebSocketService: reconnect, heartbeat, subscriptions
        │   ├── settingsApi.ts         # API клиент для settings endpoints
        │   ├── tokenApi.ts            # API клиент для token analytics endpoints
        │   ├── logger.ts              # Logger класс: transports, context, performance tracking
        │   ├── logger.config.ts       # Logger configuration (level, transports, remote)
        │   ├── logger.utils.ts        # Logger utilities (formatting, helpers)
        │   ├── index.ts               # Публичный API сервисного слоя
        │   ├── README.md              # Документация сервисного слоя
        │   └── transports/
        │       ├── ConsoleTransport.ts  # Console log transport (colored output)
        │       └── RemoteTransport.ts   # Remote log transport (batched HTTP upload)
        │
        ├── store/                     # Zustand state management
        │   ├── index.ts               # Root store: combine slices, persist, devtools
        │   ├── types.ts               # RootStore interface, slice types, Settings interface
        │   ├── selectors.ts           # Memoized selectors (messages, agents, conversation)
        │   └── slices/
        │       ├── conversationSlice.ts  # Conversation state: ID, rounds, agent messages
        │       ├── messagesSlice.ts      # Normalized messages: byId, allIds, CRUD actions
        │       ├── agentsSlice.ts        # Normalized agents: byId, allIds, status updates
        │       ├── uiSlice.ts           # UI state: processing, error, showAgentPanel
        │       ├── streamSlice.ts       # Event sourcing: handleStreamEvent (all WS events)
        │       ├── settingsSlice.ts     # Settings: load/save localStorage, validate
        │       └── historySlice.ts      # Conversation history: add, remove, search, star
        │
        ├── types/                     # TypeScript definitions
        │   ├── index.ts               # Domain types: AgentType, Message, StreamEvent, TaskRequest
        │   └── logger.ts              # Logger types: LogLevel, LogEntry, LogTransport
        │
        ├── utils/                     # Frontend утилиты
        │   ├── pdfExport.ts           # Экспорт диалога в PDF (jsPDF)
        │   ├── timeUtils.ts           # Форматирование времени (relative, absolute)
        │   └── toolParser.ts          # Парсинг tool usage из stream events
        │
        ├── shaders/                   # GLSL шейдеры для анимированного фона
        │   ├── background.vert.glsl   # Vertex shader
        │   ├── background.frag.glsl   # Fragment shader (full effect)
        │   └── background-lite.frag.glsl  # Lightweight fragment shader
        │
        └── styles/                    # CSS modules
            ├── agentToolDisplay.css
            ├── chatHistory.css
            ├── quorumSettings.css
            ├── settings.css
            ├── tokenUsage.css
            └── toolUsage.css
```

---

## 3. Внешние зависимости и их роль

### 3.1 Backend (Python)

| Зависимость | Версия | Роль в проекте |
|---|---|---|
| `fastapi` | `0.115.0` | Web-фреймворк: REST API, WebSocket, SSE endpoints |
| `uvicorn[standard]` | `0.30.6` | ASGI сервер для запуска FastAPI |
| `pydantic` / `pydantic-settings` | `2.11.10` / `2.6.1` | Валидация данных, typed settings из env |
| `langchain-core` / `langchain-openai` | `0.3.79` / `0.3.35` | LLM абстракция: ChatOpenAI, callbacks, messages |
| `sse-starlette` | `2.1.3` | Server-Sent Events для streaming responses |
| `websockets` | `13.1` | WebSocket протокол поддержка |
| `sqlalchemy` | `2.0.36` | ORM, async engine, session management |
| `asyncpg` | `0.31` | Async PostgreSQL драйвер для SQLAlchemy |
| `psycopg2` | `2.9.12` | Sync PostgreSQL драйвер (для Alembic) |
| `alembic` | `1.14.0` | Database migrations |
| `pgvector` | `0.3.6` | Vector similarity search extension для PostgreSQL |
| `redis` | `5.1.1` | Опциональный кэш/session store (флаг `USE_REDIS=false` по умолчанию) |
| `duckduckgo-search` | `7.1.1` | Web search без API ключа (провайдер по умолчанию) |
| `structlog` | `24.4.0` | Structured logging с context vars |
| `python-json-logger` | `3.2.1` | JSON формат для file logging |
| `orjson` | `3.10.7` | Быстрый JSON сериализатор |
| `httpx` | `0.27.2` | Async HTTP клиент (Tavily/SerpAPI search, testing) |
| `pytest` / `pytest-asyncio` / `pytest-cov` / `pytest-mock` | various | Testing framework |

### 3.2 Frontend (Node.js / npm)

| Зависимость | Версия | Роль в проекте |
|---|---|---|
| `react` / `react-dom` | `^18.3.1` | UI библиотека |
| `zustand` | `^4.5.5` | State management (normalized state, slices, persist) |
| `framer-motion` | `^11.5.4` | Анимации (mount/unmount, transitions) |
| `lucide-react` | `^0.441.0` | SVG иконки |
| `react-markdown` / `remark-gfm` | `^10.1.0` / `^4.0.1` | Markdown рендеринг в сообщениях |
| `jspdf` | `^3.0.3` | Генерация PDF из диалогов |
| `vite` | `^5.4.5` | Build tool и dev server |
| `typescript` | `^5.5.4` | Type safety |
| `tailwindcss` | `^3.4.11` | Utility-first CSS |
| `eslint` + plugins | various | Code linting |

### 3.3 Внешние сервисы

| Сервис | Роль | Конфигурация |
|---|---|---|
| **PostgreSQL 13+** | Основная БД: диалоги, сообщения, embeddings, settings | `DATABASE_URL` в `.env`, pgvector extension |
| **OpenRouter API** | Унифицированный доступ к LLM (Claude, GPT, Gemini, Grok) | `OPENROUTER_API_KEY` в `.env` или DB settings |
| **OpenAI API** | Embeddings для vector search (`text-embedding-3-small`) | `OPENAI_API_KEY` (через OpenRouter или прямой) |
| **Redis** (опционально) | Кэш, session store (на данный момент не используется активно) | `USE_REDIS=false` по умолчанию |
| **DuckDuckGo** | Web search без API ключа (провайдер по умолчанию) | Без конфигурации |
| **Tavily API** (опционально) | Альтернативный web search провайдер | `TAVILY_API_KEY` env var |
| **SerpAPI** (опционально) | Альтернативный web search провайдер | `SERPAPI_API_KEY` env var |

---

## 4. Стек технологий (краткая сводка)

| Слой | Технология |
|---|---|
| Backend runtime | Python 3.13+, asyncio, FastAPI, uvicorn |
| LLM integration | LangChain (ChatOpenAI → OpenRouter), callback handlers |
| Database | PostgreSQL 13+ + pgvector, SQLAlchemy 2.0 (async), Alembic |
| Real-time | WebSocket (primary), SSE (fallback REST) |
| Frontend runtime | React 18, TypeScript 5.5, Vite 5 |
| State management | Zustand 4 (slices pattern, normalized state, persist) |
| Styling | Tailwind CSS 3, Framer Motion |
| Logging | structlog (backend), custom Logger (frontend) |
| Testing | pytest + pytest-asyncio (backend), eslint (frontend) |
