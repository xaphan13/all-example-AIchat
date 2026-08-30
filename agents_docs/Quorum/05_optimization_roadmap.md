# 05 — Предложения по развитию (Optimization Roadmap)

> Конкретные рекомендации по масштабированию, производительности, рефакторингу и DX.
> Версия анализа: август 2026.

---

## 1. Приоритизация (quick wins → architectural)

| Приоритет | Категория | Задача | Ожидаемый эффект |
|---|---|---|---|
| P0 | Bug | Исправить `/health` endpoint (несуществующие поля settings) | Корректный health check |
| P0 | Security | Аутентификация + rate limiting | Защита от абьюза платных LLM API |
| P0 | Refactoring | Разбить `TaskOrchestrator` | Меньше багов, тестируемость |
| P1 | Performance | Параллельное выполнение суб-агентов | 2-3x ускорение ответа |
| P1 | Architecture | Полноценный tool calling | Работает web_search (сейчас декларативно) |
| P1 | Reliability | Persistence token usage | Аналитика переживает рестарты |
| P2 | DX | CI/CD, frontend тесты | Уверенность в изменениях |
| P2 | Performance | N+1 в conversations list, bulk inserts | Меньше latency DB |
| P3 | Architecture | Redis кэш, background tasks, WebSocket scaling | Горизонтальное масштабирование |

---

## 2. Архитектурные улучшения

### 2.1 Масштабирование под асинхронную нагрузку

#### 2.1.1 Ввести Task Queue (background processing)

**Текущее состояние**: SSE/WS-генератор живёт синхронно с запросом; долгие задачи блокируют worker'а целиком (конференция 3×3 раунда = 9 последовательных LLM-вызовов, каждый 10-120s).

**Рекомендация**: перенести тяжелую оркестрацию в background task через queue:

```
WebSocket/SSE request
  → enqueue (conversation_id, task)
  → немедленный ответ клиенту
  → Worker (asyncio task) выполняет TaskOrchestrator
  → события публикуются в Redis Pub/Sub
  → ConnectionManager подписан на каналы conversation_id → WebSocket push
```

Варианты реализации (от простого к сложному):
1. **asyncio.Task + in-memory event bus** (минимально) — события через `asyncio.Queue` per conversation, worker'ы через `asyncio.create_task`. Подходит для single-instance.
2. **Redis Streams / Redis Pub-Sub** — декомпозиция: orchestrator в отдельном процессе, WS-сервер подписывается. Масштабируется горизонтально (несколько WS-нод).
3. **Celery/RQ/ARQ** — полноценная очередь с retries, visibility timeout, dead-letter queue.

**Почему это важно**: текущая модель «1 WS-соединение = 1 занятый asyncio task» хорошо держит 10-20 пользователей, но не масштабируется: `process_task` может занимать минуты, а все эти минуты держится WS-корутина.

#### 2.1.2 Вертикальная изоляция состояния

Проблема: `ConnectionManager` и `TokenTrackingManager` — process-wide in-memory singletons. При запуске 4 uvicorn workers (`--workers 4` из README) состояние **рассинхронизируется**: connection на worker 1 не увидит broadcast с worker 2.

**Рекомендация**:
- Перенести WS-state в Redis: `conversation_subscribers` → Redis Set per conversation, `active_tasks` → Redis hash.
- `TokenTrackingManager` → Redis + периодический flush в PostgreSQL (`token_usage` таблица).
- Принять решение: **либо** sticky sessions + 1 worker для WS, **либо** внешний pub/sub (Redis). Текущий README советует `--workers 4`, что ломает WS broadcasting.

#### 2.1.3 Отказоустойчивость

| Улучшение | Реализация |
|---|---|
| Retry с exponential backoff для LLM | Настроить `ChatOpenAI(max_retries=3, timeout=...)` в `base_agent.py` |
| Circuit breaker для провайдеров | Обернуть вызовы в tenacity/polycircuit; при fallback — переключение на другой провайдер через OpenRouter |
| Dead-letter для задач | При ошибке оркестрации — логировать в отдельную очередь, уведомлять пользователя через `error` событие |
| Graceful degradation при LLM timeout | `agent_timeout` уже есть в settings — начать использовать: `asyncio.wait_for(agent.get_complete_response(...), timeout=agent_timeout)` |
| Healthcheck с реальными проверками | `/health` должен проверять: DB connectivity (`SELECT 1`), OpenRouter key валидность, WS manager state |

#### 2.1.4 Модель параллельных агентов

Заменить последовательный `_run_agent_conversation` на true parallel execution:

```python
# Файл: backend/src/core/orchestrator/task_orchestrator.py
async def _run_agent_round(self, agents, context, round_number):
    tasks = [
        self._run_agent_in_round(agent_id, agent, context, round_number)
        for agent_id, agent in self.active_sub_agents.items()
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    # stream chunk'и через asyncio.Queue или asyncio.Condition
```

Ограничение параллелизма: `asyncio.Semaphore(max_concurrent_agents)` из settings.

### 2.2 Правильная реализация tool calling

**Текущее состояние**: tools-схемы передаются в `ChatOpenAI(tools=...)`, но ответы LLM не обрабатываются. `BaseAgent.execute_tool()` существует, но никто его не вызывает.

**Рекомендация**:
1. Добавить поддержку `response.usage_metadata` / `tool_calls` в `BaseAgent.stream_response` и `get_complete_response`:
   - В `_initialize_chat_model` использовать `ChatOpenAI(bind_tools=[...])`
   - В цикле стриминга проверять `chunk.tool_call_chunks`
   - Эмитить события `tool_use` / `tool_result` (frontend уже готов — `streamSlice.ts` обрабатывает эти типы)
2. Реализовать loop: LLM → tool call → execute → результат в messages → повторный вызов LLM (max 3 итерации)
3. Для суб-агентов в конференции — передавать `tool_registry` (сейчас `_create_sub_agents` создаёт агентов **без** `tool_registry`).

### 2.3 Хранение state вне процесса

| Компонент | Сейчас | Цель |
|---|---|---|
| Token usage | in-memory list | PostgreSQL таблица + Redis hot cache |
| WS subscriptions | in-memory dict | Redis sets |
| Settings cache | in-memory | Redis (TTL) |
| Conversation history | in-memory orchestrator | DB + Redis cache с LRU eviction |

---

## 3. Оптимизация производительности

### 3.1 Backend: конкретные участки

#### 3.1.1 Убрать `asyncio.sleep(0.01)` в SSE loop — P1

Файл: `backend/src/api/routes/tasks.py:43`

```python
# Сейчас:
async for event_data in orchestrator.process_task(task):
    event_json = json.dumps(event_data)
    yield f"data: {event_json}\n\n"
    await asyncio.sleep(0.01)   # ← 10ms × N событий
```

Убрать sleep или снизить до `0.001`. Для 1000+ событий стрима экономия = секунды. (Если sleep добавлен для контроля backpressure — использовать настраиваемый `stream_delay_ms` из settings.)

#### 3.1.2 Параллелизм суб-агентов — P1

Файл: `backend/src/core/orchestrator/task_orchestrator.py`

- Активировать `_execute_sub_agents` (уже написан с `asyncio.gather`) или переписать `_run_agent_conversation` на параллельные раунды.
- Оценка: 3 агента × 3 раунда последовательно = 9 × (TTFT + generation). Параллельно = 3 × (TTFT + generation) при 3 раундах — **до 3x ускорение** (заявлено в ARCHITECTURE.md, но не реализовано).

#### 3.1.3 Лимитирование и суммаризация контекста — P1

Файл: `backend/src/core/orchestrator/task_orchestrator.py`

- `_prepare_main_agent_messages` и `_prepare_conversation_prompt` безгранично растут.
- Добавить: `max_history_messages` (например 20 последних), окно в `in_memory_history`, суммаризацию через отдельный LLM-вызов при переполнении.
- В конференции — передавать только summary предыдущих раундов, а не весь текст.

#### 3.1.4 Использовать готовую параллельную ветку `asyncio.gather` — P1

`_execute_sub_agents` уже содержит `asyncio.gather(*tasks, return_exceptions=True)`. Или интегрировать сборку. Не дублировать.

#### 3.1.5 N+1 в списке диалогов — P2

Файл: `backend/src/api/routes/conversations.py:86-109`

```python
# Сейчас: N запросов
for conv in conversations:
    messages = await MessageRepository.get_by_conversation(db, conv.id)

# Цель: 1 запрос
counts = await session.execute(
    select(Message.conversation_id, func.count(Message.id))
    .where(Message.conversation_id.in_([c.id for c in conversations]))
    .group_by(Message.conversation_id)
)
```

#### 3.1.6 Bulk insert для agent-сообщений — P2

Файл: `backend/src/api/routes/websocket.py:319-331`

`save_agent_conversation_message` вызывается в цикле → N транзакций. Добавить `ConversationService.save_agent_messages_bulk(session, messages)` с одним `session.add_all(...)`.

#### 3.1.7 DB session scope

Каждый `db_manager.session()` создаёт новую сессию из пула (pool_size=10, overflow=20). Для горячего пути (orchestrator) — использовать одну сессию на задачу. Оценить `NullPool` (сейчас не используется — в connection.py импортирован, но не применён).

#### 3.1.8 Токены: избегать двойного вызова main agent — P2

`_get_delegation_plan` выполняет полный non-streaming вызов, ответ которого не используется. Альтернативы:
- Совместить «plan» и «ответ»: попросить main agent вернуть JSON-блок в начале финального ответа и распарсить его.
- Использовать structured output (JSON mode / response_format) для гарантии парсинга.
- Ограничить делегирование keyword-based эвристикой (быстро и дёшево), а LLM-решение делать только при сложных запросах.

### 3.2 Frontend: конкретные участки

#### 3.2.1 Virtualized message list — P2

`ChatWindow` рендерит все сообщения. Подключить `react-window`/`@tanstack/react-virtual` для списков > 200 сообщений.

#### 3.2.2 Debounce persist — P2

Zustand `persist` пишет в localStorage при каждом изменении. Обернуть в debounce (например, 500ms) через `StorageWrite` custom storage.

#### 3.2.3 Батчинг WS chunk events — P2

При высокой скорости токенов `handleStreamEvent` вызывается на каждый чанк. Группировать chunk'и по 30-50ms в `requestAnimationFrame`-синхронный батч, вызывая `appendToMessage` раз за фрейм.

#### 3.2.4 Отложенный PDF export — P3

`jspdf` синхронный. Вынести в `setTimeout`/Web Worker, показывать прогресс.

### 3.3 База данных

| Оптимизация | Детали |
|---|---|
| HNSW index вместо IVFFlat | `ivfflat(lists=100)` требует обучения на данных; HNSW лучше для маленьких/растущих таблиц: `USING hnsw (embedding vector_cosine_ops)` |
| Partial index на `task_id` | Если поиск по task_id частый |
| Autovacuum / ретеншен | Политика очистки старых диалогов (например, TTL 90 дней) |
| PgBouncer для pool | При 4+ workers connection pool на 10-20 коннектов на процесс упирается в max_connections PostgreSQL |

---

## 4. Рефакторинг: приоритетные модули

### 4.1 `TaskOrchestrator` — разделить (P0, ~841 строк)

**Сейчас**: God Object с 6+ ответственностями.

**Целевая структура**:

```
backend/src/core/orchestrator/
├── task_orchestrator.py     # Связующий слой: процесс, события, cancellation (≈200 строк)
├── conversation_loader.py   # Загрузка истории из БД, in-memory windowing (extract из _load_conversation_history)
├── delegation_planner.py    # _get_delegation_plan: prompt, JSON parsing, aliases (extract)
├── agent_conference.py      # _run_agent_conversation, _create_sub_agents, _prepare_conversation_prompt
├── synthesizer.py           # _prepare_synthesis_*, _prepare_main_agent_messages
└── events.py                # Typed event-модели (dataclasses/Pydantic) вместо raw dicts
```

**Обоснование**: каждый модуль тестируется независимо; убирает дублирование alias-маппингов в module-level constant `AGENT_TYPE_ALIASES`.

### 4.2 `websocket.py` route — вынести логику в сервис (P1, ~463 строк)

**Сейчас**: route совмещает протокол + DB + lifecycle.

**Цель**: создать `ConversationSessionService` (или расширить `ConversationService`):
- `save_task_exchange(session, conversation_uuid, user_message, assistant_response, agent_messages)`
- `track_events(events)` — инкрементальный трекинг для persistence
- Оставить в route только: парсинг `WebSocketMessage`, dispatch по типу, connection lifecycle.

Также убрать неиспользуемый `persistent_orchestrator` (создаётся на строке 36, не используется).

### 4.3 `base_agent.py` — разделить на компоненты (P1)

- `ChatModelFactory` — ленивая инициализация + кэширование моделей (extract `_initialize_chat_model`)
- `MessageConverter` — `_convert_to_langchain_messages`
- Оставить `BaseAgent` как Facade.

### 4.4 `WebSearchTool` — Strategy registry (P2)

`SearchProvider` ABC → `DuckDuckGoProvider`, `TavilyProvider`, `SerpAPIProvider`. Registry для provider lookup. Убирает if/elif цепочку, упрощает добавление провайдеров (OpenAI search, Exa, Brave).

### 4.5 `streamSlice.ts` — mapper вместо монолитного switch (P1)

```typescript
// streamSlice.ts
const eventHandlers: Record<StreamEvent['type'], (ctx: HandlerCtx) => void> = {
  init: handleInit,
  agent_status: handleAgentStatus,
  stream: handleStreamChunk,
  complete: handleComplete,
  // ...
};
```

Каждый handler — отдельная чистая функция; unit-testable без store.

### 4.6 Синхронизация моделей и pricing (P1)

- Создать единый каталог моделей `backend/src/core/model_catalog.py`:
  ```python
  ModelSpec(agent_type, openrouter_id, pricing, context_window, provider)
  ```
- `AgentFactory.MODEL_MAP` и `MODEL_PRICING_CONFIG` и `QUORUM_MODELS` — читают из каталога.
- Устраняет расхождение: `AgentType.CLAUDE_MAIN = "claude-sonnet-4.5"` ↔ `"anthropic/claude-3.5-sonnet"`.

### 4.7 Исправить `health.py` (P0)

```python
# Сейчас (сломан): обращение к несуществующим settings.anthropic_api_key и т.д.
return {
    "api_keys": {"anthropic": bool(settings.anthropic_api_key), ...}  # AttributeError? Нет — вернёт... 

# На самом деле: pydantic settings с extra="ignore" вернёт None через __getattr__? Нет —
# несуществующий атрибут на BaseSettings бросает AttributeError (нет __getattr__).
# Но т.к. код в /health обёрнут... health возвращает False только если поле существует.
```

**Фикс**: проверять `settings.openrouter_api_key` и реальное состояние через `SettingsService.get_openrouter_api_key()` + DB ping.

---

## 5. Улучшение DX (Developer Experience)

### 5.1 Тесты

| Направление | Действие | Файлы |
|---|---|---|
| WS route tests | `pytest` + `httpx.AsyncClient` + `ASGITransport` | `backend/tests/test_websocket_route.py` |
| ConnectionManager tests | Unit: connect/disconnect/subscribe/broadcast | `backend/tests/test_connection_manager.py` |
| Token manager tests | Session lifecycle, aggregation, cleanup | `backend/tests/test_token_manager.py` |
| Conversations API tests | CRUD, pagination, task_id lookup | `backend/tests/test_conversations_api.py` |
| Frontend unit tests | `vitest` + `@testing-library/react` для streamSlice (чистые функции) | `frontend/src/store/__tests__/` |
| E2E | Playwright: send message → stream → complete; cancel flow | `e2e/` |
| Integration | Docker-compose (postgres+pgvector) → полный цикл: WS task → DB rows | `backend/tests/integration/` |

**Конфигурация**: frontend не имеет `test` script — добавить `vitest`, `@testing-library/react`, `jsdom`, настроить в `vite.config.ts` (`test` block).

### 5.2 CI/CD

```yaml
# .github/workflows/ci.yml (рекомендация)
name: CI
on: [push, pull_request]

jobs:
  backend:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: pgvector/pgvector:pg16
        env:
          POSTGRES_USER: quorum
          POSTGRES_PASSWORD: quorum
          POSTGRES_DB: quorum
        ports: [5432:5432]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.13' }
      - run: pip install -r backend/requirements.txt
      - run: pytest backend/tests -v
      - run: make lint

  frontend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: '20' }
      - run: cd frontend && npm ci
      - run: cd frontend && npm run lint
      - run: cd frontend && npx tsc --noEmit
      - run: cd frontend && npm run build
      - run: cd frontend && npm test
```

Pipeline для деплоя: build → docker image → push → helm/k8s или docker-compose на VPS.

### 5.3 Локальный запуск

| Улучшение | Детали |
|---|---|
| Docker-compose для dev | `docker-compose.yml`: postgres:16-pgvector + backend + frontend; `make dev` поднимает всё |
| `.env.example` vs `config/env_template.txt` | Перенести в корень backend/.env.example (распространённый конвеншн) |
| Makefile: `make setup` | Автоматический запуск postgres (docker), создание .env из шаблона, миграции |
| Alembic autogenerate | Настроить первый baseline migration; заменить `create_all` на `alembic upgrade head` в lifespan |
| Pre-commit hooks | `ruff` (lint+format), `mypy` (backend), `eslint --fix`, `prettier` (frontend), `typecheck` |
| Task runner | Один `justfile`/`Makefile` target: `make dev` — оба сервиса + hot reload |
| OpenAPI/Swagger | FastAPI уже генерирует — добавить ссылку в README (`/docs`) |
| `.env` валидация | При старте проверять: `OPENROUTER_API_KEY` пустой → warning в startup лог |

### 5.4 Мониторинг

| Инструмент | Что собирать |
|---|---|
| Prometheus + FastAPI middleware | `requests_total`, `request_duration_histogram`, `active_ws_connections`, `agent_llm_calls_total` |
| OpenTelemetry | Distributed tracing: WS task → orchestrator → LLM → DB (trace_id через correlation_id) |
| Sentry | Обработка исключений на backend (`SENTRY_DSN`), frontend (`@sentry/react`) |
| Grafana dashboards | Token cost per model/day, error rates, P95 latency |
| Healthcheck провайдеров | OpenRouter uptime: cron `/health` + alerting |

---

## 6. Roadmap: фазы

### Phase 1 — Stability & Correctness (1-2 недели)
- [ ] Fix `/health` (несуществующие поля settings)
- [ ] Fix `websocket.py`: удалить неиспользуемый `persistent_orchestrator`
- [ ] Убрать дублирование `agent_type_aliases` (module constant)
- [ ] Включить `agent_timeout` в LLM-вызовы (`asyncio.wait_for`)
- [ ] Удалить мёртвый код (`_execute_sub_agents`, `_prepare_synthesis_messages`, неиспользуемые модели)

### Phase 2 — Performance (2-3 недели)
- [ ] Параллельные суб-агенты (`asyncio.gather` + `Semaphore`)
- [ ] Убрать `asyncio.sleep(0.01)` из SSE
- [ ] Контекстное окно + суммаризация истории
- [ ] N+1 fix в conversations list
- [ ] Bulk insert для agent-сообщений

### Phase 3 — Security & Auth (3-4 недели)
- [ ] JWT-аутентификация (fastapi-users или custom)
- [ ] Rate limiting (slowapi / middleware на Redis)
- [ ] Шифрование API key в БД (cryptography Fernet)
- [ ] Убрать `mask_keys=false` публичный параметр
- [ ] CORS ограничить методы

### Phase 4 — Scalability (4-8 недель)
- [ ] Redis Pub/Sub для WS broadcasting (multi-worker)
- [ ] Token usage persistence в PostgreSQL
- [ ] Task queue для долгих оркестраций
- [ ] PgBouncer / pool tuning
- [ ] Docker-compose + k8s манифесты

### Phase 5 — Tool calling & Extensibility (6-8 недель)
- [ ] Полный tool calling loop в `BaseAgent`
- [ ] `model_catalog.py` единый источник моделей/pricing
- [ ] Strategy pattern для search providers
- [ ] RAG: активировать `VectorService` в flow (embeddings при сохранении сообщений)

---

## 7. Оценка трудозатрат

| Задача | Оценка (чел-дни) | Критичность |
|---|---|---|
| Fix health endpoint | 0.5 | 🔴 P0 |
| Auth + rate limiting | 5-10 | 🔴 P0 |
| Рефакторинг TaskOrchestrator | 5-7 | 🔴 P0 |
| Параллельные суб-агенты | 2-3 | 🟠 P1 |
| Tool calling loop | 5-8 | 🟠 P1 |
| Context windowing/summarization | 2-4 | 🟠 P1 |
| Token usage persistence | 3-5 | 🟠 P1 |
| WebSocket multi-worker (Redis) | 5-10 | 🟡 P2 |
| CI/CD + frontend tests | 3-5 | 🟡 P2 |
| Virtualized list (frontend) | 2-3 | 🟡 P2 |
| HNSW index + DB tuning | 1-2 | 🟢 P3 |
| E2E tests (Playwright) | 3-5 | 🟢 P3 |
| Redis caching layer | 3-7 | 🟢 P3 |

**Итого Phase 1-2**: ~15-25 чел-дней (стабилизация + производительность).
**Итого Phase 3-5**: ~30-55 чел-дней (полная промышленная готовность).
