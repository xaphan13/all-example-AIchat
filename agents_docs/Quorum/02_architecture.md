# 02 — Архитектура и паттерны (Architecture & Patterns)

> Детальный разбор архитектуры NoOversight / Quorum.
> Версия анализа: август 2026.

---

## 1. Высокоуровневая архитектура

### 1.1 Общая характеристика

Система построена по **слоистой монолитной архитектуре** с асинхронным ядром. Это не микросервисы — всё backend-приложение работает в едином процессе uvicorn. Однако внутри соблюдено чёткое слоистое разделение:

```
┌─────────────────────────────────────────────────────────┐
│                    PRESENTATION LAYER                     │
│  React SPA (Vite) ← WebSocket / SSE → FastAPI Routes     │
├─────────────────────────────────────────────────────────┤
│                    API LAYER                              │
│  FastAPI Routers + Middleware (logging, CORS, perf)      │
│  Routes: tasks, websocket, conversations, settings,     │
│          tokens, health                                  │
├─────────────────────────────────────────────────────────┤
│                  BUSINESS LOGIC LAYER                     │
│  TaskOrchestrator (multi-agent coordination)             │
│  AgentFactory + BaseAgent (LLM interaction)              │
│  SettingsService (DB → env fallback)                     │
│  ToolRegistry + BaseTool (extensible tools)              │
├─────────────────────────────────────────────────────────┤
│                INFRASTRUCTURE LAYER                       │
│  DatabaseManager (SQLAlchemy async, PostgreSQL)          │
│  ConnectionManager (WebSocket connections)               │
│  TokenTrackingManager (in-memory usage analytics)        │
│  structlog (structured logging with context vars)        │
│  VectorService (OpenAI embeddings + pgvector search)     │
└─────────────────────────────────────────────────────────┘
```

### 1.2 Backend-frontend взаимодействие

Система поддерживает **два транспортных канала**:

1. **WebSocket** (`/ws`) — основной канал. Двунаправленная связь: клиент отправляет task-запросы, stop-команды, ping/pong; сервер стримит события (init, agent_status, stream, complete и др.). Используется в production-режиме frontend.

2. **SSE** (`POST /api/task/stream`) — fallback через REST. Однонаправленный стрим от сервера к клиенту. Используется как альтернатива WebSocket.

Оба транспорта используют единый `TaskOrchestrator` для обработки, но WebSocket поддерживает персистентный orchestrator на соединение (сохранение контекста диалога между сообщениями).

### 1.3 Frontend архитектура

React SPA с **slice-based Zustand store**:

```
App.tsx (orchestrator component)
  ├── useWebSocket hook → WebSocketService (singleton)
  │     └── onMessage → store.handleStreamEvent(event)
  │
  ├── Zustand Store (single source of truth)
  │     ├── conversationSlice  (conversationId, rounds)
  │     ├── messagesSlice      (normalized: byId, allIds)
  │     ├── agentsSlice        (normalized: byId, allIds)
  │     ├── uiSlice            (isProcessing, error, showPanel)
  │     ├── streamSlice        (event sourcing: handleStreamEvent)
  │     ├── settingsSlice      (localStorage persistence)
  │     └── historySlice       (conversation history)
  │
  └── Components (presentational + container)
        ├── ChatWindow / ChatInput / MessageBubble
        ├── AgentPanel / AgentCard / AgentConversation
        ├── ChatHistory (left sidebar)
        └── Settings (modal)
```

---

## 2. Основные паттерны проектирования

### 2.1 Factory Pattern — `AgentFactory`

Файл: `backend/src/agents/agent_factory.py`

`AgentFactory` инкапсулирует создание агентов с правильной конфигурацией:

```python
class AgentFactory:
    MODEL_MAP = {AgentType.CLAUDE_MAIN: "anthropic/claude-3.5-sonnet", ...}
    SYSTEM_PROMPTS = {AgentType.CLAUDE_MAIN: "...", ...}

    @classmethod
    def create_main_agent(cls, session_id, tool_registry) -> BaseAgent: ...
    @classmethod
    def create_sub_agent(cls, agent_type, task_description, ...) -> BaseAgent: ...
```

Изолирует логику маппинга `AgentType → OpenRouter model ID` и system prompts от потребителя.

### 2.2 Repository Pattern — `*Repository`

Файлы: `backend/src/infrastructure/database/repository.py`, `settings_repository.py`

Три репозитория предоставляют статические async-методы для CRUD операций:

- `ConversationRepository` — `create`, `get_by_id`, `get_by_task_id`, `list_recent`, `update`, `delete`
- `MessageRepository` — `create`, `get_by_id`, `get_by_conversation`, `get_by_agent`
- `EmbeddingRepository` — `create`, `get_by_message`, `similarity_search`, `search_conversations`
- `SettingsRepository` — `get_or_create`, `get`, `update`, `to_dict`

Репозитории работают с `AsyncSession` и не управляют её жизненным циклом — сессия передаётся извне.

### 2.3 Service Layer Pattern — `ConversationService`, `SettingsService`

Файлы: `backend/src/infrastructure/database/conversation_service.py`, `backend/src/core/settings_service.py`

`ConversationService` — orchestration layer над репозиториями:
- `get_or_create_conversation()` — поиск по task_id/UUID, создание если не найден
- `save_user_message()` / `save_assistant_message()` / `save_agent_conversation_message()` — сохранение с трекингом
- `get_conversation_with_messages()` — загрузка с eager loading

`SettingsService` — унифицированный доступ к настройкам с каскадным fallback:
```
Database (AppSettings table) → Cached settings → Environment variables
```

### 2.4 Singleton Pattern (модульные синглтоны)

Используется через глобальные переменные модуля:

| Синглтон | Файл | Метод получения |
|---|---|---|
| `db_manager` | `infrastructure/database/connection.py` | Прямой импорт |
| `connection_manager` | `infrastructure/websocket/manager.py` | Прямой импорт |
| `settings` | `core/config.py` | Прямой импорт |
| `_token_manager` | `infrastructure/tracking/token_manager.py` | `get_token_manager()` |
| `_settings_service` | `core/settings_service.py` | `get_settings_service(db_manager)` |
| `_global_registry` | `tools/registry.py` | `get_tool_registry()` |

### 2.5 Strategy Pattern — `WebSearchTool` providers

Файл: `backend/src/tools/web_search.py`

`WebSearchTool` поддерживает 3 провайдера через internal strategy:

```python
if self.provider == "duckduckgo":
    results = await self._search_duckduckgo(...)
elif self.provider == "tavily":
    results = await self._search_tavily(...)
elif self.provider == "serpapi":
    results = await self._search_serpapi(...)
```

### 2.6 Event Sourcing (frontend) — `streamSlice`

Файл: `frontend/src/store/slices/streamSlice.ts`

Все изменения состояния frontend управляются через единый обработчик `handleStreamEvent(event)`. Каждый WS-событие → switch-case → мутация соответствующего slice. Это **event sourcing pattern**: события являются единственным источником изменений состояния.

```typescript
handleStreamEvent: (event: StreamEvent) => {
  switch (event.type) {
    case 'init':          → initConversation, setProcessing(true)
    case 'agent_status':  → updateAgent / addAgent
    case 'stream':        → appendToMessage / addMessage
    case 'complete':      → setProcessing(false), saveCurrentConversation
    case 'agent_message_chunk': → appendToAgentMessage / addAgentMessage
    // ... 15+ event types
  }
}
```

### 2.7 Normalized State (frontend)

Файл: `frontend/src/store/types.ts`

Messages и Agents хранятся в **нормализованном виде** для O(1) lookups:

```typescript
interface NormalizedMessages {
  byId: Record<string, Message>;   // O(1) by ID
  allIds: string[];                 // Ordered list
}
```

Селекторы (`selectors.ts`) денормализуют данные для компонентов, вычисляя массивы из `allIds.map(id => byId[id])`.

### 2.8 Observer / Callback Pattern — `TokenTrackingCallback`

Файл: `backend/src/infrastructure/tracking/callback_handler.py`

`TokenTrackingCallback` реализует `AsyncCallbackHandler` из LangChain. Подписывается на lifecycle events LLM:
- `on_llm_start` — логирование начала
- `on_llm_end` — извлечение token usage из response (поддержка OpenAI/Anthropic/Google форматов)
- `on_llm_error` — логирование ошибок

Callback передаёт `TokenUsage` в `TokenTrackingManager` через `on_usage_callback`.

### 2.9 Template Method — `BaseTool`

Файл: `backend/src/tools/base.py`

`BaseTool` — ABC с абстрактными методами `name`, `description`, `parameters`, `execute()`. Конкретные инструменты (`WebSearchTool`) наследуются и реализуют абстракции. Базовый класс предоставляет `get_schema()` (генерация OpenAI function schema) и `validate_parameters()`.

### 2.10 Middleware Chain (FastAPI)

Файл: `backend/src/app.py`, `backend/src/api/middleware/logging.py`

```
Request → CORSMiddleware → LoggingMiddleware → [PerformanceLoggingMiddleware] → Route Handler
```

- `LoggingMiddleware` — correlation ID, request/response logging, duration tracking
- `PerformanceLoggingMiddleware` — warning при slow requests (>1000ms), включается только в DEBUG

---

## 3. Схема потока данных (Data Flow)

### 3.1 Основной цикл: WebSocket task processing

```
┌─────────┐     1. WS connect (/ws)      ┌──────────────────┐
│  React  │ ───────────────────────────→ │ ConnectionManager │
│  App    │ ←──── 2. "connected" ────── │ .connect()        │
└────┬────┘                              └──────────────────┘
     │
     │ 3. sendTask({ message, enableCollaboration, maxSubAgents })
     ▼
┌──────────────────┐
│  WS Endpoint     │  4. WebSocketMessage(type="task", task=TaskRequest)
│  (websocket.py)  │
└────────┬─────────┘
         │
         │ 5. ConversationService.get_or_create_conversation()
         │    ConversationService.save_user_message()
         ▼
┌──────────────────┐
│ TaskOrchestrator │  6. process_task(task: TaskRequest) → AsyncGenerator
│ .process_task()  │
└────────┬─────────┘
         │
         │ 7. _load_conversation_history() (DB → in-memory)
         │ 8. AgentFactory.create_main_agent()
         │ 9. yield { type: "init", conversationId }
         │ 10. yield { type: "agent_status", status: "thinking" }
         ▼
    ┌────────────────────────────────────────┐
    │  enable_collaboration == true ?        │
    └───────────────┬────────────────────────┘
                    │ YES
                    ▼
┌──────────────────┐                          11. _get_delegation_plan()
│ Main Agent       │ ──────────────→   Main agent.get_complete_response()
│ (Claude 3.5)     │                   с delegation_prompt → JSON { delegate, sub_queries }
└────────┬─────────┘
         │ 12. delegate == true
         ▼
┌──────────────────┐     13. _create_sub_agents(sub_queries)
│ Sub-Agents       │     AgentFactory.create_sub_agent() for each
│ (Claude Haiku,   │
│  GPT-4o, etc.)   │     14. _run_agent_conversation() — multi-round:
└────────┬─────────┘       for round in 1..3:
         │                   for each agent:
         │                     yield { type: "agent_thinking" }
         │                     agent.stream_response() → yield { "agent_message_chunk" }
         │                     yield { type: "agent_message", isComplete: true }
         │                   yield { type: "conversation_round_complete" }
         ▼
┌──────────────────┐
│ Main Agent       │  15. _prepare_synthesis_from_conversation()
│ (synthesis)      │      main_agent.stream_response(synthesis_messages)
└────────┬─────────┘
         │
         │ 16. yield { type: "stream", content: chunk } (token-by-token)
         │ 17. yield { type: "complete", finalResponse }
         ▼
┌──────────────────┐
│  WS Endpoint     │  18. Broadcast all events via ConnectionManager
│  (websocket.py)  │  19. ConversationService.save_assistant_message()
│                  │      ConversationService.save_agent_conversation_message()
│                  │  20. token_manager.close_session() + log stats
└────────┬─────────┘
         │
         ▼
┌─────────┐     21. WS events received      ┌──────────────────┐
│  React  │ ←───────────────────────────── │ WebSocketService  │
│  App    │                                 │ .onMessage()      │
└────┬────┘                                 └──────────────────┘
     │
     │ 22. store.handleStreamEvent(event)
     │     → streamSlice: switch(event.type)
     │     → messagesSlice: addMessage / appendToMessage
     │     → agentsSlice: addAgent / updateAgent
     │     → uiSlice: setProcessing / setError
     ▼
┌─────────┐
│  React  │  23. Re-render (Zustand selectors trigger)
│  UI     │      ChatWindow, AgentPanel, etc.
└─────────┘
```

### 3.2 Альтернативный путь: SSE (REST)

```
POST /api/task/stream → event_generator(task, session_id)
  → TaskOrchestrator.process_task(task)
  → yield SSE: "data: {json}\n\n"
  → Frontend: APIService.streamTask() → fetch + ReadableStream reader
```

### 3.3 Database interaction pattern

Все DB-операции идут через `db_manager.session()` — async context manager:

```python
async with db_manager.session() as db_session:
    # auto-commit on success, auto-rollback on exception
    result = await SomeRepository.method(db_session, ...)
# session closed automatically
```

FastAPI routes используют dependency injection: `db: AsyncSession = Depends(get_db)`.

---

## 4. Управление состоянием, кэширование и конфигурации

### 4.1 Управление состоянием

#### Backend

| Компонент | Хранение | Scope |
|---|---|---|
| `TaskOrchestrator` | In-memory: `in_memory_history`, `conversation_rounds`, `active_sub_agents` | Per-WebSocket connection (persistent orchestrator) или per-request (REST) |
| `ConnectionManager` | In-memory: `active_connections`, `conversation_subscribers`, `active_tasks` | Process-wide singleton |
| `TokenTrackingManager` | In-memory: `sessions`, `global_usage` (list) | Process-wide singleton, данные теряются при рестарте |
| `SettingsService` | In-memory: `_cached_settings` | Process-wide singleton, invalidate_cache() при обновлении |

#### Frontend

| Компонент | Хранение | Persistence |
|---|---|---|
| Zustand store | In-memory (JS runtime) | `persist` middleware → `localStorage` (key: `quorum-store`) |
| Persisted slices | `localStorage` | conversation metadata, messages (normalized), agents, settings, history |
| Ephemeral slices | In-memory only | UI state (isProcessing, error), stream state (isStreaming, currentStreamId) |

### 4.2 Кэширование

| Что | Где | Стратегия |
|---|---|---|
| AppSettings | `SettingsService._cached_settings` | Читается из БД при первом доступе, инвалидация через `invalidate_cache()` (вызывается при `PUT /api/settings`) |
| LangChain ChatModel | `BaseAgent._chat_model` / `_chat_model_streaming` | Ленивая инициализация, кэшируется до `refresh_api_keys()` или `set_tool_registry()` |
| Conversation history | `TaskOrchestrator.in_memory_history` | Загружается из БД один раз (`history_loaded_from_db`), затем поддерживается in-memory |
| Frontend store | Zustand + `localStorage` | `partialize()` фильтрует ephemeral state; version=1, auto-migrate |

### 4.3 Конфигурация

#### Иерархия (приоритет убывает)

1. **Database** (`app_settings` table) — runtime-обновляемые настройки через `PUT /api/settings`
2. **Environment variables** (`.env` файл в `backend/`) — загружаются через `pydantic-settings`
3. **Code defaults** — в `Settings` class (`backend/src/core/config.py`)

```python
class Settings(BaseSettings):
    openrouter_api_key: str = ""           # default
    database_url: str = "postgresql://quorum:quorum@localhost:5432/quorum"
    max_concurrent_agents: int = 5
    log_level: str = "INFO"
    # ...
    model_config = SettingsConfigDict(env_file=".env", ...)
```

#### Ключевые переменные окружения

| Переменная | Назначение | Default |
|---|---|---|
| `OPENROUTER_API_KEY` | API ключ для LLM доступа | `""` |
| `DATABASE_URL` | PostgreSQL connection string | `postgresql://quorum:quorum@localhost:5432/quorum` |
| `HOST` / `PORT` | Bind address для uvicorn | `0.0.0.0` / `8000` |
| `CORS_ORIGINS` | Разрешённые CORS origins (comma-separated) | `http://localhost:3000,http://localhost:5173` |
| `MAX_CONCURRENT_AGENTS` | Лимит параллельных агентов | `5` |
| `AGENT_TIMEOUT` | Таймаут агента (секунды) | `120` |
| `LOG_LEVEL` | Уровень логирования | `INFO` |
| `LOG_JSON` | JSON-формат логов (production) | `false` |
| `USE_REDIS` | Включить Redis (не активно) | `false` |
| `EMBEDDING_MODEL` | Модель для embeddings | `text-embedding-3-small` |
| `EMBEDDING_DIMENSION` | Размерность векторов | `1536` |

#### Frontend конфигурация

- `VITE_API_BASE` — backend URL (default: `http://localhost:8000`)
- `VITE_WS_BASE` — WebSocket URL (default: `ws://localhost:8000`)
- Vite proxy: `/api` → `http://localhost:8000` (для dev режима)
- Runtime settings: `localStorage` через `settingsSlice`

---

## 5. Модель данных (Database Schema)

### 5.1 ER-структура

```
┌──────────────────────┐       ┌──────────────────────┐
│    conversations      │       │      messages         │
├──────────────────────┤       ├──────────────────────┤
│ id (UUID, PK)        │←──────│ id (UUID, PK)        │
│ title (VARCHAR 500)  │  1:N  │ conversation_id (FK)  │
│ task_id (VARCHAR 255)│       │ role (VARCHAR 50)     │
│ created_at (TIMESTAMZ)│      │ content (TEXT)        │
│ updated_at (TIMESTAMZ)│      │ agent_id (VARCHAR 255)│
│ metadata (JSONB)     │       │ agent_type (VARCHAR)  │
└──────────────────────┘       │ sequence_number (INT) │
          ↑                    │ created_at (TIMESTAMZ)│
          │  1:N               │ input_tokens (INT)    │
          │                    │ output_tokens (INT)   │
          │                    │ total_cost (FLOAT)    │
          │                    │ metadata (JSONB)      │
          │                    └──────────────────────┘
          │                            ↑ 1:1 (optional)
          │                            │
┌──────────────────────┐       ┌──────────────────────┐
│     embeddings        │       │    app_settings       │
├──────────────────────┤       ├──────────────────────┤
│ id (UUID, PK)        │       │ id (UUID, PK)         │
│ conversation_id (FK) │       │ openrouter_api_key    │
│ message_id (FK, uniq)│       │ max_concurrent_agents │
│ embedding (VECTOR)   │       │ agent_timeout         │
│ model (VARCHAR 100)  │       │ embedding_model       │
│ text_content (TEXT)  │       │ embedding_dimension   │
│ created_at (TIMESTAMZ)│      │ vector_sim_threshold  │
│ metadata (JSONB)     │       │ theme, notifications  │
└──────────────────────┘       │ log_level             │
                               │ created_at, updated_at│
                               └──────────────────────┘
```

### 5.2 Индексы

| Индекс | Таблица | Колонки | Тип |
|---|---|---|---|
| `idx_messages_conversation_sequence` | messages | (conversation_id, sequence_number) | B-tree |
| `idx_messages_created_at` | messages | created_at | B-tree |
| `idx_conversations_created_at` | conversations | created_at | B-tree |
| `idx_embeddings_conversation` | embeddings | conversation_id | B-tree |
| `idx_embeddings_vector` | embeddings | embedding | IVFFlat (cosine) |

### 5.3 pgvector

Расширение `vector` включается при инициализации (`CREATE EXTENSION IF NOT EXISTS vector`). Используется для:
- Semantic search сообщений (`EmbeddingRepository.similarity_search`)
- Поиск похожих диалогов (`EmbeddingRepository.search_conversations`)
- IVFFlat index с `lists=100` и `vector_cosine_ops`

---

## 6. Token tracking и cost analytics

### 6.1 Поток трекинга

```
BaseAgent._initialize_chat_model()
  → создаёт TokenTrackingCallback (streaming + non-streaming варианты)
  → callbacks=[callback] передаётся в ChatOpenAI

LLM call (ainvoke / astream)
  → LangChain вызывает callback.on_llm_end(response)
  → _extract_usage_from_response() (OpenAI / Anthropic / Google formats)
  → создаёт TokenUsage(model_id, input_tokens, output_tokens, cost)
  → on_usage_callback → TokenTrackingManager.record_usage(usage, session_id)
```

### 6.2 Хранение

`TokenTrackingManager` хранит данные **in-memory** (не персистентно):
- `sessions: Dict[str, SessionUsage]` — per-session агрегация
- `global_usage: List[TokenUsage]` — все записи (линейный рост)
- `asyncio.Lock` для thread safety

### 6.3 Pricing

Хардкод в `backend/src/core/token_models.py` → `MODEL_PRICING_CONFIG`:
- 8 моделей (OpenAI, Anthropic, Google, X.AI)
- Цены per 1K tokens (input/output)
- Context window sizes
- `calculate_cost(input, output)` метод

---

## 7. Безопасность (Security Architecture)

### 7.1 API Keys

- Хранятся в `.env` (env vars) или в `app_settings` таблице (БД)
- Никогда не передаются на frontend (только masked: `sk-or-...xxxx`)
- `SettingsService` обеспечивает fallback: DB → env
- `censor_sensitive_data` в structlog — редacting ключей в логах

### 7.2 CORS

- Whitelist origins через `CORS_ORIGINS` env var
- `allow_credentials=True`, `allow_methods=["*"]`, `allow_headers=["*"]`

### 7.3 SQL Injection

- SQLAlchemy ORM с parameterized queries
- pgvector operations через SQLAlchemy expressions
- Нет raw SQL (кроме `CREATE EXTENSION` и `SELECT 1`)

### 7.4 Input Validation

- Pydantic модели для всех request/response (`TaskRequest`, `WebSocketMessage`, и др.)
- Валидация в `BaseTool.validate_parameters()`
- FastAPI automatic validation через type hints

### 7.5 Известные пробелы

- **Нет rate limiting** (отмечено в `ARCHITECTURE.md` как TODO)
- **Нет аутентификации/авторизации** — API полностью открыт
- **Нет шифрования API keys в БД** (comment: "encrypted in production", но не реализовано)
- **WebSocket без аутентификации** — любой клиент может подключиться
