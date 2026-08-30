# 04 — Оценка качества кодовой базы (Code Quality)

> Аудит читаемости, модульности, соответствия SOLID/DRY/KISS, выявление техдолга и узких мест.
> Версия анализа: август 2026.

---

## 1. Общая оценка

| Критерий | Оценка (1-10) | Комментарий |
|---|---|---|
| Читаемость | 8/10 | Понятные имена, структурированный код, обширные docstrings |
| Модульность | 8/10 | Чёткое слоистое разделение, репозитории/сервисы/фабрики |
| Связность (cohesion) | 7/10 | Высокая внутри слоёв, но есть cross-layer зависимости (orchestrator → DB напрямую) |
| Документация кода | 8/10 | docstrings на всех публичных методах, но комментарии местами устарели |
| Тестируемость | 6/10 | Много глобальных синглтонов, сложно мокать; тесты есть, но неполные |
| Современность | 7/10 | Python 3.13, async/await, SQLAlchemy 2.0 typed API, но есть legacy следы |

**Итоговая оценка: 7.3/10** — solid mid-tier кодовая база с заметными возможностями для улучшения.

---

## 2. Соответствие принципам SOLID

### S — Single Responsibility

**✅ Соответствует:**
- `ConversationService` — только persistence логика диалогов
- `TokenTrackingCallback` — только извлечение token usage
- `TokenTrackingManager` — только агрегация и аналитика
- `ConnectionManager` — только управление WS-соединениями
- Frontend slices — каждый отвечает за свою доменную область

**⚠️ Нарушения:**
- `TaskOrchestrator` (841 строка) выполняет 6+ ответственностей: загрузка истории из БД, делегирование, меж-агентную конференцию, синтез, стриминг, cancellation. Файл стоит разбить на `ConversationLoader`, `DelegationPlanner`, `AgentConference`, `ResponseSynthesizer`.
- `BaseAgent` (414 строк) — одновременно LLM-клиент, конвертер сообщений, tool-executor и token-tracker.
- `websocket.py` route (463 строки) — хендлер совмещает парсинг протокола, оркестрацию сохранений в БД, управление подписками и lifecycle orchestrator'ов.

### O — Open/Closed

**✅ Соответствует:**
- `BaseTool` ABC + `ToolRegistry` — новые инструменты добавляются без модификации существующего кода
- `AgentFactory` MODEL_MAP/SYSTEM_PROMPTS — добавление агента = новая запись в маппинг

**⚠️ Нарушения:**
- `_extract_usage_from_response` в `callback_handler.py` — цепочка if/elif для форматов провайдеров; новый провайдер = модификация существующего кода (нужен Strategy/Registry для парсеров).
- `handleStreamEvent` в `streamSlice.ts` (529 строк, 20+ case) — новый тип события = модификация монолитного switch. Стоит вынести в mapper событие→обработчик.
- `WebSearchTool` — добавление провайдера требует правки существующего `execute()` (нарушает OCP).

### L — Liskov Substitution

**✅ Соответствует:**
- Все наследники `BaseTool` соблюдают контракт интерфейса
- Все `*Repository` имеют единообразные сигнатуры

**⚠️ Нет нарушений, требующих внимания.**

### I — Interface Segregation

**✅ Соответствует:**
- Frontend slice interfaces (`ConversationSlice`, `MessagesSlice`, и т.д.) — узкие интерфейсы

**⚠️ Нарушения:**
- `RootStore` объединяет 7 slice интерфейсов + глобальный `reset()` — для consumer'ов это монолитный интерфейс, но это осознанный компромисс Zustand-паттерна.

### D — Dependency Inversion

**✅ Соответствует:**
- Repositories принимают `AsyncSession` (абстракцию)
- `SettingsService` принимает `DatabaseManager` через конструктор

**⚠️ Нарушения:**
- **Глобальные синглтоны**: `get_token_manager()`, `get_settings_service()`, `db_manager`, `connection_manager` создаются в коде модулей. Тестирование требует monkey-patching глобальных объектов (видно в `pytest.ini` с `asyncio_default_fixture_loop_scope`).
- `TaskOrchestrator` импортирует `ConversationRepository` напрямую внутри метода (`from src.infrastructure.database.repository import ConversationRepository`) — скрытая зависимость.
- `VectorService` создаёт `AsyncOpenAI` client в конструкторе — хардкод зависимости.

---

## 3. DRY (Don't Repeat Yourself)

**✅ Хорошо:**
- `_mask_api_key` — единая функция маскирования
- `selectMessages`/`selectAgents` — единый паттерн денормализации
- `to_camel` alias_generator — единообразные camelCase контракты
- `_convert_to_langchain_messages` — единая конвертация форматов

**⚠️ Дублирование:**

1. **Agent type aliases** — маппинг `agent_type_aliases = {"gpt-4": AgentType.GPT5, ...}` определён **дважды**: в `_execute_sub_agents()` и в `_create_sub_agents()` (`task_orchestrator.py`, строки ~421 и ~574). Нужен module-level constant.

2. **Session summary logging** — блок «close session + log stats» повторяется в `tasks.py` (SSE, ~5 строк) и `websocket.py` (finally block, ~12 строк).

3. **MessageResponse построение** — ручное конструирование `MessageResponse(...)` повторяется 3 раза в `conversations.py` (get_conversation, get_conversations_by_task × 2).

4. **Event processing guards** — паттерн «ignore if streaming ended» и «ignore if agent complete» повторяется в `streamSlice.ts` для 4+ типов событий.

5. **Pricing каталог** — `MODEL_PRICING_CONFIG` (8 моделей) не синхронизирован с `MODEL_MAP`/`QUORUM_MODELS` в `AgentFactory`; дублирование фактических данных в двух местах.

---

## 4. KISS (Keep It Simple)

**✅ Соответствует:**
- Отказ от тяжёлых фреймворков (LangGraph/CrewAI) в пользу лёгкого кастомного orchestrator'а
- Прямое использование Zustand вместо Redux
- SSE проще WebSocket для однонаправленных потоков

**⚠️ Усложнения:**
- `websocket.py` route содержит сложную логику «rekeying» orchestrator'а (`active_conversation_orchestrators[actual_conv_id] = ...pop(conv_id)`) — хрупкое состояние, легко ошибиться
- Двойной механизм трекинга токенов (streaming и non-streaming callbacks) — сложно следить за тем, какой используется
- `_get_delegation_plan` полагается на сырой JSON-парсинг ответа LLM — хрупко; лучше использовать structured output / function calling

---

## 5. Выявленный технический долг

### 5.1 Устаревшая/несоответствующая документация

| Файл | Проблема |
|---|---|
| `ARCHITECTURE.md` | Упоминает `litellm`, но фактически используется `langchain-openai` + OpenRouter base_url; упоминает `/api/task/stream` path, но фронтенд использует WebSocket; описывает `main.py` — реальный файл `src/app.py` |
| `README.md` | Документирует SSE `/api/tasks/execute` и `/api/conversations/{id}/messages` — таких эндпоинтов нет; описывает `/api/task/stream` как основной, но frontend идёт через WS |
| `health.py` | Обращается к `settings.anthropic_api_key`, `settings.openai_api_key`, `settings.google_api_key` — **этих полей не существует** в `Settings` (есть только `openrouter_api_key`). Всё возвращает `False` всегда. |
| `base_agent.py` docstring | Упоминает «LiteLLM integration», фактически — LangChain |
| `task_orchestrator.py` | Метод `_execute_sub_agents()` (параллельное выполнение) **не используется** в текущем flow (используется `_run_agent_conversation` — последовательный). Мёртвый код с лишними alias-маппингами. |
| `requirements.txt` | Содержит `redis` и `pgvector`, `asyncpg`, но: Redis не используется (флаг false), VectorService использует OpenAI API напрямую |

### 5.2 Мёртвый код

| Код | Где | Примечание |
|---|---|---|
| `_execute_sub_agents` / `_execute_single_sub_agent` | `task_orchestrator.py` | Не вызываются из `process_task` |
| `_prepare_synthesis_messages` | `task_orchestrator.py` | Заменён на `_prepare_synthesis_from_conversation`, не используется |
| `EmbeddingRepository` / `VectorService` | database layer | Описан и реализован, но нигде не вызывается в request flow (embeddings не создаются при сохранении сообщений) |
| `redis` / `USE_REDIS` | config, requirements | Не используется |
| `utils/cost_calculator.py` | backend | Дублирует функциональность `TokenTrackingManager.calculate_projected_costs`/`get_cost_comparison` |
| `Message`, `AgentResponse` | `core/models.py` | Часть моделей не используется в актуальном потоке (task processing возвращает dict'ы, а не Pydantic-модели) |
| `tool_use` / `tool_result` события | frontend types + streamSlice | Backend их не эмитит; обработка есть, но фактически тупиковая (tool calling не реализован в BaseAgent) |

### 5.3 Несогласованность имён и данных

1. **`AgentType` enum** (`core/models.py`): `CLAUDE_MAIN = "claude-sonnet-4.5"`, но `MODEL_MAP` (`agent_factory.py`) маппит его на `anthropic/claude-3.5-sonnet`. Значения enum не соответствуют фактическим моделям.
2. **`QUORUM_MODELS`** в `AgentFactory` — содержит `google/gemini-2.0-flash-exp` и `x-ai/grok-beta`, но `MODEL_PRICING_CONFIG` и delegation prompt (`_get_delegation_plan`) разрешают только `claude-sonnet-3.5` и `gpt-5`. Несогласованность между рекламируемыми и реально доступными агентами.
3. **WebSocket save** хардкодит `agent_type="claude-sonnet-4.5"` для main agent при сохранении в БД, тогда как фактические model = `anthropic/claude-3.5-sonnet`.
4. **`settings.py` route** содержит endpoint `GET /api/settings/api-keys/validate` при prefix `/api/settings` — путь фактически `/api/settings/api-keys/validate`, что читается странно.

### 5.4 Архитектурный техдолг

1. **Token tracking полностью in-memory** — потеря данных при рестарте. Нет персистентности, несмотря на поля `input_tokens`/`output_tokens`/`total_cost` в таблице `messages`.
2. **Conversation персистентность только для WebSocket-пути** — REST SSE путь не сохраняет сообщения в БД (только session stats).
3. **`Base.metadata.create_all` в lifespan** — используется вместо полноценных миграций Alembic (alembic настроен, но `versions/` пуст).
4. **Settings double-source of truth** — env vars + DB таблица, синхронизация только через `invalidate_cache`.
5. **Два оркестратора-инстанса на один WS-connection** — создаётся `persistent_orchestrator` в начале (`websocket.py:36`), который **не используется**, плюс per-conversation orchestrator'ы в `active_conversation_orchestrators`.

---

## 6. Запахи кода (Code Smells)

### 6.1 God Object

- **`TaskOrchestrator`** (841 строк) — центральный God Object. Содержит бизнес-логику, DB-загрузку, LLM-координацию, стриминг.
- **`streamSlice.ts` handleStreamEvent** (529 строк, 20+ case) — God Method.
- **`WebSearchTool`** (301 строка) — три провайдера в одном классе.

### 6.2 Data Clumps / Magic Numbers

- `max_conversation_rounds = 3` — hardcoded
- `max_sub_agents: 3` — продублирован в `App.tsx` (taskRequest) и `TaskRequest` default
- `await asyncio.sleep(0.01)` в SSE generator и `0.5` между раундами — magic
- `len(key) > 10` / `len(key) > 30` — магические пороги валидации API key в трёх местах
- `lists=100` для IVFFlat index — хардкод

### 6.3 Feature Envy

- `websocket.py` route выполняет работу, которая должна жить в сервисе: манипуляции с `active_conversation_orchestrators`, DB-сохранения, сбор `agent_messages`.

### 6.4 Inconsistent abstraction

- Часть кода использует Pydantic-модели (`TaskRequest`, `StreamChunk`), часть — сырые dict'ы (все события из orchestrator). Переход на typed event-модели облегчит поддержку.

### 6.5 Long parameter lists

- `MessageRepository.create(...)` — 11 параметров
- `ConversationService.save_assistant_message(...)` — 9 параметров
- `AgentFactory.create_agent(...)` — 8 параметров (оправдано)

---

## 7. Узкие места (Bottlenecks)

### 7.1 Backend

| Узкое место | Файл | Анализ |
|---|---|---|
| **`asyncio.sleep(0.01)` на каждый SSE event** | `tasks.py:43` | Добавляет 10ms × N events задержку к каждому стриму. При 500 событиях — 5s чистой задержки |
| **Последовательные суб-агенты** | `_run_agent_conversation` | Агенты работают по очереди; `asyncio.gather` (параллелизм) написан, но не используется. 3 агента × 3 раунда = 9 последовательных LLM-вызовов |
| **Полный контекст каждого раунда** | `_prepare_conversation_prompt` | Каждый раунд включает ВСЕ предыдущие сообщения + full context — O(rounds²) рост токенов |
| **In-memory token tracking** | `token_manager.py` | `global_usage` растёт без ограничений, каждый запрос — O(n) по всей истории (aggregation) |
| **Двойной LLM-вызов для делегирования** | `_get_delegation_plan` | Main agent вызывается ДВАЖДЫ: один раз для плана (non-streaming) + один раз для финального ответа (streaming). Первый ответ отбрасывается полностью |
| **`list_recent` + N+1 запросы** | `conversations.py:86-109` | Для каждого диалога в списке выполняется отдельный `get_by_conversation` для подсчёта сообщений (N+1). |
| **Контекст диалога без лимита** | `_prepare_main_agent_messages` | Вся история из in-memory передаётся в LLM без обрезки/суммаризации — проблемы с context window на длинных диалогах |
| **Sequential DB writes после стрима** | `websocket.py:301-345` | Сохранение всех agent-сообщений по одному в цикле (нет bulk insert) |

### 7.2 Frontend

| Узкое место | Анализ |
|---|---|
| **Батчинг WS-событий** | Каждый чанк → `handleStreamEvent` → set() → потенциальный re-render; при высокой частоте токенов могут быть проблемы производительности |
| **Поток полного диалога в localStorage** | Zustand persist сериализует все сообщения при каждом изменении — для длинных диалогов может блокировать main thread |
| **RemoteTransport** | Отправляет логи на remote endpoint без queue/retry policy (flush каждые 5s) |
| **Нет virtualized list** | `ChatWindow` рендерит все сообщения сразу; для диалогов на 1000+ сообщений — деградация |
| **PDF экспорт (jsPDF)** | Синхронный рендеринг в main thread — потенциальный фриз UI на больших диалогах |

---

## 8. Оценка безопасности

### 8.1 Существующие меры

| Мера | Статус |
|---|---|
| API keys в env/БД (не в git) | ✅ |
| API key masking в API response | ✅ `_mask_api_key` |
| Censoring sensitive data в логах | ✅ `censor_sensitive_data` (structlog) |
| CORS whitelist | ✅ |
| SQL injection protection (ORM) | ✅ |
| Pydantic input validation | ✅ |
| Correlation IDs для трейсинга | ✅ |

### 8.2 Проблемы безопасности

| Проблема | Критичность | Файл |
|---|---|---|
| **Отсутствие аутентификации** на всех API endpoints | 🔴 HIGH | Все routes |
| **Отсутствие rate limiting** | 🔴 HIGH | Вся система — любой может дёргать платные LLM API |
| **Отсутствие авторизации** для `PUT /api/settings` | 🔴 HIGH | `settings.py:79` — любой может сменить API key |
| **`GET /api/settings?mask_keys=false`** позволяет получить полный API key | 🟠 MEDIUM | `settings.py:53,68` — «for authenticated requests only», но аутентификации нет |
| **API keys в открытом виде в БД** | 🟠 MEDIUM | `settings_models.py:29` — комментарий «encrypted in production», шифрования нет |
| **WebSocket без аутентификации** | 🟠 MEDIUM | `websocket.py:20` |
| **Данные сессий не очищаются** | 🟡 LOW | `TokenTrackingManager` — in-memory, но cleanup endpoint без auth |
| **CORS `allow_methods=["*"]`, `allow_headers=["*"]`** | 🟡 LOW | Широкие полномочия |
| **JWT не используется**, ключ может утечь в логи через `logger.info` при debug | 🟡 LOW | `settings.py:86` логирует только имена полей — ок; `web_search.py:106` логирует query без key — ок |

### 8.3 Надёжность

| Аспект | Оценка | Комментарий |
|---|---|---|
| Graceful degradation (DB down) | ✅ | Приложение продолжает работать |
| Обработка разрыва соединений | ✅ | WS disconnect → cleanup, SSE → stream_end |
| **Retry для LLM-вызовов** | ❌ | Отсутствует; ошибка → ошибка пользователю |
| **Таймауты для LLM-вызовов** | ⚠️ | `agent_timeout=120` в настройках, но НЕ передаётся в `ChatOpenAI` (нет `timeout=`/`max_retries=`) |
| **Idempotency** | ❌ | Повторная отправка задачи создаёт дубликаты в БД |
| **Утечка ресурсов: WS connections** | ✅ | `ConnectionManager.disconnect` чистит всё |
| **Утечка: `active_conversation_orchestrators`** | ✅ | Чистится в finally |
| **Утечка: `TokenTrackingManager.global_usage`** | ⚠️ | Неограниченный рост в памяти, cleanup только вручную через API |

---

## 9. Тестовое покрытие и его пробелы

### 9.1 Существующие тесты (`backend/tests/`)

| Файл | Покрывает |
|---|---|
| `test_config.py` | Settings: defaults, env vars |
| `test_models.py` | Pydantic-модели: валидация, alias |
| `test_base_agent.py` | BaseAgent: stream/complete response, message conversion |
| `test_agent_factory.py` | AgentFactory: model mapping, prompts |
| `test_task_orchestrator.py` | Orchestrator: delegation, synthesis, streaming |
| `test_tools.py` | Tools: registry, schemas, validation |
| `test_main.py` | App: lifespan, middleware, routes |

### 9.2 Пробелы

| Пробел | Риск |
|---|---|
| Нет тестов `websocket.py` route (самый сложный файл) | Высокий |
| Нет тестов `conversations.py` CRUD | Средний |
| Нет тестов `ConnectionManager` | Средний |
| Нет тестов `TokenTrackingManager` | Средний |
| Нет integration-тестов с реальной БД (или mocks) | Высокий |
| Frontend не имеет тестов вообще (нет `test` script в package.json) | Высокий |
| Нет e2e тестов | Высокий |

---

## 10. Итоговая сводка

### Сильные стороны
1. Чистая слоистая архитектура backend с разделением API/бизнес/инфраструктура
2. Асинхронный код с правильным использованием async/await
3. Хорошая структурированность frontend: нормализованный store, селекторы, slices
4. Структурированное логирование с correlation IDs и цензурированием
5. Грамотная система graceful degradation
6. Расширяемость через Tool Registry и AgentFactory

### Критические проблемы (требуют немедленного внимания)
1. `health.py` ссылается на несуществующие поля `settings.anthropic_api_key` и др. — health check врёт
2. Нет аутентификации/rate limiting — при публичном деплое это уязвимость с денежными потерями
3. `_execute_sub_agents` параллельный режим не используется — производительность ниже заявленной в 3x

### Приоритетный техдолг
1. Разбить `TaskOrchestrator` на модули
2. Устранить дублирование alias-маппингов
3. Реализовать полноценный tool calling (сейчас tools декларированы, но не исполняются)
4. Добавить миграции Alembic (сейчас create_all)
5. Персистентность token usage
