# 03 — Логика и работа кода (Execution Flow)

> Step-by-step разбор жизненного цикла приложения, бизнес-процессов, роутинга, ошибок и логирования.
> Версия анализа: август 2026.

---

## 1. Жизненный цикл приложения

### 1.1 Инициализация backend

```
Процесс запуска uvicorn (src.app:app)
  │
  ├─ 1. Модуль src.core.config выполняется:
  │     settings = Settings()  ← pydantic-settings читает .env, применяет defaults
  │
  ├─ 2. src.app импортируется:
  │     setup_logging(log_level, json_logs, log_file)  ← structlog конфигурация
  │     logger = get_logger(__name__)
  │
  ├─ 3. create_app() выполняется на этапе модуля:
  │     app = FastAPI(title, version, lifespan=lifespan)
  │     CORS middleware
  │     LoggingMiddleware (exclude: "/", "/health")
  │     PerformanceLoggingMiddleware (только если LOG_LEVEL == DEBUG)
  │     6 routers: health, tasks, websocket, tokens, settings, conversations
  │
  └─ 4. uvicorn стартует → вызывается lifespan
```

### 1.2 Lifespan manager (startup)

Файл: `backend/src/app.py`

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- STARTUP ---
    logger.info("application_starting", host, port, log_level)

    try:
        # 1. Инициализация DB engine + session factory
        await db_manager.initialize()

        # 2. Enable pgvector extension
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))

        # 3. Create all tables если отсутствуют
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(AppSettings.metadata.create_all)

        # 4. SettingsService с DB-backed settings
        settings_service = get_settings_service(db_manager)

    except Exception as e:
        # DB недоступен → приложение продолжает работу без БД
        logger.error("database_initialization_failed", exc_info=True)
        get_settings_service()   # env-only mode

    yield

    # --- SHUTDOWN ---
    logger.info("application_shutdown")
    await db_manager.close()    # dispose async engine
```

**Ключевое поведение**: при недоступности БД приложение запускается в degraded mode (используются только env-настройки, персистентность не работает).

### 1.3 Frontend lifecycle

```
main.tsx → ReactDOM.createRoot → <App/>
  │
  ├─ useWebSocket({ autoConnect: true })  ← WebSocketService.connect() (singleton)
  │     → WS connection → { type: "connected" } → connectionId сохранён
  │     → auto-reconnect с exponential backoff (max 10 attempts)
  │     → heartbeat ping каждые 30s
  │
  ├─ useEffect: loadSettings() ← localStorage (zustand persist)
  │
  ├─ ErrorBoundary оборачивает всё приложение
  │
  └─ Компоненты рендерятся:
      Header (status indicator, settings button)
      ChatHistory (left panel)
      ChatWindow (center) + ChatInput + ErrorBanner
      AgentPanel (right, conditional)
```

### 1.4 Завершение работы

**Backend:**
- `SIGINT/SIGTERM` → uvicorn graceful shutdown → `lifespan` yield resume → `db_manager.close()` (dispose engine, закрытие всех пулов)
- WS-соединения закрываются клиентом или по таймауту
- `ConnectionManager.disconnect()` очищает: connections, subscriptions, metadata, sessions
- `TokenTrackingManager.close_session()` финализирует статистику сессий

**Frontend:**
- `unmount` → cleanup: unsubscribe handlers, disconnect WS (если autoConnect=false)
- Store persist автоматически сохраняет изменения в `localStorage`

---

## 2. Ключевые бизнес-процессы

### 2.1 Процесс: обработка задачи (Task Processing)

**Entry point**: `POST /api/task/stream` (SSE) или `WS /ws` → `{type: "task"}`

#### Phase 0 — Подготовка

**REST-путь** (`backend/src/api/routes/tasks.py`):
1. Валидация `message` не пуста (HTTP 400)
2. Создание `session_id = "session_rest_{uuid}"`
3. `token_manager.create_session(session_id)`
4. `EventSourceResponse(event_generator(task, session_id))` — SSE headers: `Cache-Control: no-cache`, `X-Accel-Buffering: no`

**WebSocket-путь** (`backend/src/api/routes/websocket.py`):
1. Парсинг `WebSocketMessage` через Pydantic
2. `ConversationService.get_or_create_conversation()` — поиск/создание в БД
3. `ConversationService.save_user_message()` — пользовательское сообщение в БД
4. Поиск существующего orchestrator в `active_conversation_orchestrators` (persistent контекст)
5. `connection_manager.register_task(conv_id, ws_orchestrator)` — для поддержки stop
6. Auto-subscribe к conversation

#### Phase 1 — Инициализация (TaskOrchestrator.process_task)

Файл: `backend/src/core/orchestrator/task_orchestrator.py`

1. `conversation_id` = из task или новый `conv_{uuid}` 
2. `bind_context(conversation_id=...)` — контекст логирования
3. Загрузка истории из БД (только первый раз, дальше in-memory):
   - Если ID формата `conv_xxx` → поиск через `get_by_task_id`
   - Если UUID → прямой поиск
   - Фильтр: пропускаются сообщения с `metadata.message_type == "agent_conversation"`
4. Создание main agent: `AgentFactory.create_main_agent(session_id)`
5. `yield { type: "init", conversationId }` — клиент узнаёт реальный ID
6. `yield { type: "agent_status", status: "thinking" }`

#### Phase 2 — Решение о делегировании

1. `_get_delegation_plan(user_message, max_sub_agents, conversation_history)`
2. Формируется `delegation_prompt` с инструкцией вернуть JSON:
   ```json
   {"delegate": true/false, "reasoning": "...", "sub_queries": [{"agent_type": "...", "query": "...", "priority": 1}]}
   ```
3. Main agent делает **non-streaming** вызов `get_complete_response()`
4. JSON парсится (с поддержкой markdown code blocks)
5. При ошибке парсинга → `{"delegate": False, "reasoning": "Error in delegation"}` (graceful degradation)

#### Phase 3 — Inter-agent конференция (если delegate == true)

`_run_agent_conversation(user_message)`:
1. `max_conversation_rounds = 3` (hardcoded)
2. Для каждого раунда (1..3):
   - Для каждого суб-агента (sequentially!):
     - `yield { type: "agent_thinking" }`
     - Формирование prompt с полным контекстом предыдущих раундов
     - `agent.stream_response(messages)` — **token-by-token** стриминг
     - `yield { type: "agent_message_chunk" }` — каждый чанк
     - После завершения: `yield { type: "agent_message", isComplete: true }`
   - `yield { type: "conversation_round_complete" }`
   - `await asyncio.sleep(0.5)` — пауза между раундами
3. Контекст раунда накапливается в `conversation_context`

**Важно**: суб-агенты внутри раунда работают **последовательно**, а не параллельно, несмотря на наличие `_execute_sub_agents()` (метод существует, но не используется в текущем WebSocket-потоке).

#### Phase 4 — Синтез и финальный ответ

1. `_prepare_synthesis_from_conversation()` — все раунды вставляются в synthesis prompt
2. Main agent `stream_response()` — финальный ответ стримится:
   - `yield { type: "stream", content: chunk }` — каждый токен
   - Проверка `is_cancelled` на каждом чанке
3. `yield { type: "complete", finalResponse }`
4. `in_memory_history` обновляется (user + assistant)
5. `unbind_context("conversation_id")`

#### Phase 5 — Persistence и финализация

**WebSocket-путь**:
1. `ConversationService.save_assistant_message()` — финальный ответ в БД
2. `ConversationService.save_agent_conversation_message()` — каждое agent-сообщение
3. `connection_manager.unregister_task(actual_conv_id)`
4. `connection_manager.unsubscribe_from_conversation()`
5. Orchestrator **остаётся** в `active_conversation_orchestrators` для сохранения контекста

**REST-путь**:
1. `token_manager.close_session(session_id)`
2. Логирование session summary (cost, tokens, requests, duration)
3. `yield { type: "stream_end" }` — гарантированное завершение SSE

### 2.2 Процесс: отмена генерации (Cancel/Stop)

```
Client: WS send { type: "stop", conversationId: "conv_xxx" }
  │
  ├─ ConnectionManager.cancel_task(conversation_id)
  │     → orchestrator.cancel() → is_cancelled = True
  │
  ├─ TaskOrchestrator.process_task() проверяет is_cancelled:
  │     • Перед анализом → yield { type: "cancelled" }
  │     • Во время stream_response → yield { type: "cancelled", partialResponse }
  │
  └─ Client получает "cancelled" → streamSlice:
        setProcessing(false), isStreaming=false
        Все активные агенты → status: "error", message: "Cancelled"
```

### 2.3 Процесс: загрузка conversation history

```
Frontend ChatHistory.loadConversation(conversationId)
  │
  └─ GET /conversations/{id}?include_messages=true
        │
        ├─ uuid.UUID(conversation_id) — валидация формата
        ├─ ConversationRepository.get_by_id(db, conv_uuid, include_messages)
        ├─ MessageRepository.get_by_conversation(db, conv_uuid)
        └─ ConversationResponse(id, title, messages[], ...)
```

### 2.4 Процесс: web search tool

```
Main agent при вызове web_search:
  │
  ├─ LLM получает tools schema (chat_model initialized с tool_kwargs["tools"])
  │
  └─ (на текущий момент tool call processing НЕ реализован в BaseAgent.stream_response)
       BaseAgent.execute_tool(tool_name, **kwargs) существует,
       но orchestrator не обрабатывает tool_calls из LLM responses.
       System prompts описывают синтаксис, но полная интеграция отсутствует.
```

---

## 3. Роутинг и middleware

### 3.1 Полная карта эндпоинтов

| Метод | Path | Файл | Описание |
|---|---|---|---|
| GET | `/` | `routes/health.py` | Базовый health check |
| GET | `/health` | `routes/health.py` | Детальный health check (API keys presence) |
| POST | `/api/task/stream` | `routes/tasks.py` | Task processing через SSE |
| POST | `/api/task` | `routes/tasks.py` | Task processing (полный ответ) |
| POST | `/api/reset` | `routes/tasks.py` | Сброс (no-op, backwards compat) |
| WS | `/ws` | `routes/websocket.py` | WebSocket endpoint |
| GET | `/conversations` | `routes/conversations.py` | Список диалогов (pagination) |
| GET | `/conversations/{id}` | `routes/conversations.py` | Диалог с сообщениями |
| GET | `/conversations/task/{task_id}` | `routes/conversations.py` | Диалоги по task_id |
| DELETE | `/conversations/{id}` | `routes/conversations.py` | Удаление диалога |
| PATCH | `/conversations/{id}` | `routes/conversations.py` | Обновление title |
| GET | `/api/settings` | `routes/settings.py` | Настройки (masked API key) |
| PUT | `/api/settings` | `routes/settings.py` | Обновление настроек |
| GET | `/api/settings/api-keys/validate` | `routes/settings.py` | Проверка API key |
| GET | `/api/tokens/pricing` | `routes/tokens.py` | Все модели pricing |
| GET | `/api/tokens/pricing/{model_id}` | `routes/tokens.py` | Pricing конкретной модели |
| POST | `/api/tokens/calculate` | `routes/tokens.py` | Расчёт стоимости |
| POST | `/api/tokens/compare` | `routes/tokens.py` | Сравнение моделей |
| GET | `/api/tokens/stats/global` | `routes/tokens.py` | Глобальная статистика |
| GET | `/api/tokens/stats/session/{id}` | `routes/tokens.py` | Статистика сессии |
| GET | `/api/tokens/usage/recent` | `routes/tokens.py` | Недавний usage |
| GET | `/api/tokens/usage/timerange` | `routes/tokens.py` | Usage за период |
| POST | `/api/tokens/session/create/{id}` | `routes/tokens.py` | Создание сессии |
| POST | `/api/tokens/session/close/{id}` | `routes/tokens.py` | Закрытие сессии |
| DELETE | `/api/tokens/cleanup` | `routes/tokens.py` | Очистка старых данных |

### 3.2 WebSocket протокол

#### Client → Server

| Тип | Payload | Действие |
|---|---|---|
| `ping` | — | Heartbeat → `pong` |
| `subscribe` | `{conversation_id}` | Подписка на события диалога |
| `unsubscribe` | `{conversation_id}` | Отписка |
| `task` | `{task: TaskRequest}` | Запуск обработки задачи |
| `stop` | `{conversation_id}` | Отмена активной задачи |

#### Server → Client

| Тип | Payload | Назначение |
|---|---|---|
| `connected` | `{connection_id, session_id}` | Подтверждение соединения |
| `pong` | — | Ответ на heartbeat |
| `subscribed` / `unsubscribed` | `{conversation_id}` | Подтверждение подписки |
| `init` | `{conversation_id}` | Старт обработки задачи |
| `agent_status` | `{agent_id, status, message}` | Смена статуса агента |
| `delegation` | `{sub_agents, queries}` | Решение о делегировании |
| `agent_thinking` | `{agent_id, round_number}` | Агент начал думать |
| `agent_message_chunk` | `{message_id, agent_id, content}` | Токен агента |
| `agent_message` | `{message_id, content, isComplete}` | Полное сообщение агента |
| `conversation_round_complete` | `{round_number, message_count}` | Раунд завершён |
| `stream` | `{agent_id, content, is_final}` | Токен финального ответа |
| `complete` | `{conversation_id, final_response}` | Задача завершена |
| `cancelled` | `{partial_response}` | Задача отменена |
| `error` | `{error}` | Ошибка |
| `stop_acknowledged` / `stop_failed` | `{success}` | Ответ на stop |

### 3.3 Middleware chain

```
Входящий HTTP request
  │
  ├─ CORSMiddleware (allow_origins from settings)
  │
  ├─ LoggingMiddleware
  │     ├─ exclude_paths = {"/", "/health"}
  │     ├─ Correlation ID: X-Correlation-ID / X-Request-ID / generated uuid4
  │     ├─ bind_context(correlation_id, method, path, client_ip)
  │     ├─ logger.info("request_started", query_params, user_agent)
  │     ├─ response.headers["X-Correlation-ID"] = correlation_id
  │     ├─ logger.info("request_completed", status_code, duration_ms)
  │     ├─ on exception: logger.error("request_failed", exc_info=True)
  │     └─ finally: clear_context()
  │
  ├─ PerformanceLoggingMiddleware (ONLY если LOG_LEVEL == DEBUG)
  │     └─ logger.warning("slow_request_detected") если duration > 1000ms
  │
  └─ Route handler (router)
```

---

## 4. Механизмы обработки ошибок

### 4.1 Backend error handling strategy

| Уровень | Механизм | Примеры |
|---|---|---|
| FastAPI | `HTTPException` | 400 (invalid conversation UUID), 404 (not found), 500 (internal) |
| Pydantic | ValidationError при входе | Невалидный `WebSocketMessage`, пустой `message` |
| Orchestrator | Try/except + graceful degradation | Ошибка парсинга JSON делегирования → `delegate: False` |
| BaseAgent | Try/except + StreamChunk error | Ошибка LLM → `yield StreamChunk(content="Error: ...", is_final=True, metadata={"error": True})` |
| SSE generator | Try/except + error event | `yield {type: "error"}` → stream продолжается |
| WS endpoint | try/except → `send_personal_message({type: "error"})` | Ошибка обработки сообщения |
| DB | Исключения оборачиваются и логируются | `failed_to_save_conversation_to_db` (WS продолжает работу) |
| DatabaseManager.session() | Commit/rollback/close | Auto-rollback при exception, session всегда закрывается |

### 4.2 Frontend error handling

| Уровень | Механизм |
|---|---|
| React | `ErrorBoundary` (файл `components/ErrorBoundary.tsx`) — fallback UI при render-ошибках |
| WebSocket | `useWebSocket` → `setError(err)` → `App.setError` → ErrorBanner |
| Store | `uiSlice.error` + `clearError()` |
| Stream events | `case 'error'` → `setError()`, `setProcessing(false)` |
| API | `APIService` → throw Error с текстом HTTP response |

### 4.3 Graceful degradation (ключевые сценарии)

1. **PostgreSQL недоступен** → lifespan продолжается, SettingsService работает на env vars, WS-задачи работают, но история не персистируется.
2. **OpenRouter недоступен** → `BaseAgent.get_complete_response()` бросает ошибку → orchestrator ловит в `_get_delegation_plan` → отвечает без делегирования; `stream_response` возвращает ошибку в чанке.
3. **Невалидный agent_type от LLM** → alias mapping (`gpt-4` → `gpt-5`) или пропуск агента с логом ошибки.
4. **Разрыв SSE-соединения** → исключение в `event_generator` → error event → stream_end.
5. **WS send error** → `_send_with_error_handling` → `disconnect(connection_id)`.

---

## 5. Логирование

### 5.1 Backend: structlog

**Конфигурация**: `backend/src/infrastructure/logging/config.py`

**Процессоры (order matters)**:
1. `merge_contextvars` — слияние context vars из structlog.contextvars
2. `add_log_level` — добавление уровня
3. `add_logger_name` — имя логгера
4. `add_app_context` — `app=no-oversight`, `service=backend`
5. `TimeStamper(fmt="iso")` — ISO timestamp
6. `PositionalArgumentsFormatter` — поддержка position args
7. `StackInfoRenderer`
8. `censor_sensitive_data` — маскировка ключей: `api_key`, `token`, `password`, `secret`, `authorization` → `***REDACTED***` (рекурсивно)

**Форматы**:
- `JSON_LOGS=true` → JSONRenderer (production, для log aggregation)
- `LOG_JSON=false` → ConsoleRenderer с цветами (dev)

**Файл**: `LOG_FILE=path` → RotatingFileHandler (10MB × 5 backups) с JSON formatter.

**Context binding**:
```python
bind_context(conversation_id=..., correlation_id=...)  # структурированный контекст
unbind_context("conversation_id")
clear_context()  # per-request cleanup
```

**Ключевые события логирования**:
- `request_started` / `request_completed` / `request_failed` (middleware)
- `task_orchestration_started` / `task_orchestration_completed`
- `delegation_approved` / `delegation_parsing_error`
- `agent_stream_completed` / `agent_stream_error`
- `session_token_usage_summary` (после каждой задачи)
- `slow_request_detected` (perf middleware)
- `websocket_connected` / `websocket_disconnected`

### 5.2 Frontend: custom Logger

**Архитектура**: `frontend/src/services/logger.ts`

- Класс `Logger` с `transports` (ConsoleTransport + RemoteTransport + custom)
- Context stack: `createChild(context)` / `setContext` / `clearContext`
- Performance tracking: `startPerformance` / `endPerformance` / `measure`
- Session ID генерируется при создании
- `createLogger({ component: 'X' })` — фабрика child loggers

**Транспорты**:
- `ConsoleTransport` — цветной вывод в консоль
- `RemoteTransport` — батчированная отправка на remote endpoint (batchSize=10, flushInterval=5000ms)

**Ключевые события**:
- `Stream event: {type}` — каждый WS-событие (INFO, с эмодзи)
- `WebSocket connected/disconnected`
- `Task request prepared`
- `Conversation reset complete`
- Performance marks: `send-message`, `streamTask`

### 5.3 Correlation: полный поток запроса

```
Frontend WS message "task"
  → Backend LoggingMiddleware bind (для REST) / task bind_context(conversation_id)
  → TaskOrchestrator bind_context(conversation_id)
  → BaseAgent логирует с agent_id
  → TokenTrackingCallback логирует с run_id (request_id)
  → Все записи имеют: app, service, timestamp, level, logger_name, conversation_id
```