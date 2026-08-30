# Коллекция из 6 AI-чат-проектов

Репозиторий содержит **шесть независимых проектов** чат-приложений с LLM — от простого
одномодельного чата до enterprise RAG-системы и мульти-агентной платформы. Каждый проект
лежит в своей папке, подробная документация — в `agents_docs/<имя проекта>/`.

## Состав репозитория

| # | Папка | Проект | Что делает |
|---|-------|--------|------------|
| 1 | [`AI-Chatbot/`](AI-Chatbot/) | AI Chatbot Assistant | Простой чат с авторизацией: запрос → ответ одной модели (GitHub Models) |
| 2 | [`GroqStreamChain/`](GroqStreamChain/) | GroqStreamChain | Real-time чат с потоковой передачей токенов через WebSocket (Groq) |
| 3 | [`llm-council-karpathy/`](llm-council-karpathy/) | LLM Council | «Совет LLM»: несколько моделей отвечают, анонимно рецензируют, председатель синтезирует |
| 4 | [`openai-responses-python-quickstart/`](openai-responses-python-quickstart/) | OpenAI Responses Quickstart | Шаблон чата на Responses API с инструментами (code, files, MCP, computer use) |
| 5 | [`Quorum/`](Quorum/) | NoOversight (Quorum) | Мульти-агентная платформа: оркестратор + специализированные sub-agents |
| 6 | [`rag-knowledge-base-chatbot/`](rag-knowledge-base-chatbot/) | Support AI Assistant | Enterprise RAG-чатбот поддержки с гибридным поиском и цитатами |
| — | [`agents_docs/`](agents_docs/) | Документация | Полная документация по всем 6 проектам (единый источник истины) |

## Технологии

| | AI-Chatbot | GroqStreamChain | LLM Council | OpenAI Responses | Quorum | RAG Chatbot |
|---|---|---|---|---|---|---|
| **LLM-провайдер** | GitHub Models (GPT-4o) | Groq Cloud | OpenRouter (4+ модели) | OpenAI | OpenRouter + LangChain | OpenAI + compatible |
| **Бэкенд** | FastAPI, SQLAlchemy 2.0, FastAPI-Users, Alembic | FastAPI, WebSocket, groq SDK | FastAPI, httpx (async) | FastAPI, openai SDK 2.0, playwright | FastAPI, LangChain, PostgreSQL + pgvector | FastAPI, Celery, PostgreSQL, OpenSearch, Qdrant, Redis, MinIO |
| **Стриминг** | нет | WebSocket | SSE | SSE | WebSocket + SSE | SSE (псевдо) |
| **Auth** | JWT + Cookie | нет | нет | нет | нет | JWT + API-key + Admin-key |
| **Хранилище** | SQLite | in-memory | JSON-файлы | сторона OpenAI | PostgreSQL | PG + OpenSearch + Qdrant |
| **Фронтенд** | Jinja2 + Tailwind (SSR) | Vanilla JS | React 19 + Vite 7 | Jinja2 + HTMX | React 18 + TS + Zustand | React 19 + Vite 7 + Tailwind 4 |
| **Python** | 3.13 | 3.13 | 3.10+ | 3.12+ | 3.13 | 3.11+ |

## Кратко о каждом проекте

### 1. AI-Chatbot
Монолитный чат: регистрация/логин (FastAPI-Users, JWT в cookie), страница чата,
`POST /api/chat` → GitHub Models (`openai/gpt-4o`). Без истории диалога и стриминга.
Бесплатный инференс через `GITHUB_TOKEN`. Самый простой проект — хорошая точка входа.

### 2. GroqStreamChain
Real-time чат на WebSocket (`/ws/chat`): история сессий in-memory, ответ LLM стримится
чанками через нативный Groq SDK (`llama-3.1-8b-instant` по умолчанию, меняется через
`MODEL_NAME`). Демонстрация минимальной задержки, без БД и auth.

### 3. LLM Council
Реализация идеи Andrej Karpathy. Три стадии: (1) 4 модели параллельно отвечают,
(2) анонимно ранжируют ответы друг друга (`FINAL RANKING`, «Street Cred»),
(3) модель-председатель синтезирует финальный ответ. OpenRouter, SSE-стриминг,
диалоги в JSON-файлах.

### 4. OpenAI Responses Quickstart
Официальный шаблон на Responses API (преемник Assistants API). Состояние диалога хранится
на стороне OpenAI (Conversations API). 7 типов инструментов: code interpreter, file search,
custom functions, MCP (с approval-флоу), web search, computer use (Playwright).
Настройка модели и инструментов через веб-UI `/setup`. Голосовой ввод через Whisper.

### 5. Quorum (NoOversight)
Мульти-агентная платформа: main agent получает задачу, строит план делегирования,
создаёт специализированных sub-agents (Claude Haiku, GPT-4o), проводит до 3 раундов
конференции и синтезирует ответ. PostgreSQL + pgvector, трекинг токенов и стоимости,
React + TypeScript + Zustand фронтенд.

### 6. RAG Knowledge Base Chatbot
Enterprise-чатбот поддержки. Гибридный поиск (BM25 в OpenSearch + векторы в Qdrant → RRF →
reranker), пайплайн `UNDERSTAND → RETRIEVE → ASSESS_EVIDENCE → DECIDE → GENERATE → VERIFY`,
ответы с цитатами и confidence, эскалация при нехватке доказательств. База знаний
наполняется документами, краулером WHMCS-тикетов и непрерывным обучением на одобренных
тикетах. Самый сложный проект: Celery, MinIO, OpenTelemetry, админская SPA.

## Документация

Полная документация в [`agents_docs/`](agents_docs/) — по единому шаблону на проект:

- `01_project_structure.md` — структура и карта модулей
- `02_architecture.md` — архитектура и конфигурация
- `03_execution_flow.md` — жизненный цикл запроса
- `04_code_quality.md` — техдолг и безопасность
- `05_optimization_roadmap.md` — план улучшений (P0–P3)
- `06_*` — фронтенд; `07_*` — AI-модели и провайдеры; `08+` — примеры и доп. материалы

Для AI-ассистентов: см. [`AGENTS.md`](AGENTS.md) — правила навигации и маршрутизации
вопросов по проектам.
