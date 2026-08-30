# 07 — Отчёт по работе приложения с AI-моделями

> Обзор того, как NoOversight / Quorum взаимодействует с LLM: архитектура слоя агентов,
> жизненный цикл запроса, трекинг токенов и текущие ограничения.
> Версия анализа: август 2026.

---

## 1. Общая картина

Приложение работает с языковыми моделями **не напрямую**, а через два уровня абстракции:

```
Frontend (React) ──WS/SSE──▶ FastAPI Routes
                                 │
                                 ▼
                        TaskOrchestrator          ← бизнес-логика, делегирование
                                 │
                    ┌────────────┴────────────┐
                    ▼                         ▼
              BaseAgent (main)          BaseAgent × N (sub-agents)
                    │                         │
                    └────────────┬────────────┘
                                 ▼
                     LangChain ChatOpenAI
                                 │
                                 ▼
                  OpenRouter API (openai-compatible)
                                 │
            ┌──────────┬─────────┼─────────┬──────────┐
            ▼          ▼         ▼         ▼          ▼
        Anthropic   OpenAI    Google    X.AI      +300 др.
```

Ключевые факты:

- **Единая точка доступа к LLM** — OpenRouter (`https://openrouter.ai/api/v1`),
  OpenAI-совместимый API. Один ключ `OPENROUTER_API_KEY` открывает доступ к моделям
  Anthropic, OpenAI, Google, X.AI и сотням других без отдельных интеграций.
- **LLM-слой** — `langchain-openai.ChatOpenAI` с `base_url`, переключённым на OpenRouter
  (`backend/src/agents/base_agent.py:100-108`).
- **Всё асинхронно**: `ainvoke` (целый ответ) и `astream` (потоковая генерация по токенам).
- **Каждый вызов LLM сопровождается трекингом токенов** через LangChain callback
  (`TokenTrackingCallback`), стоимость считается по встроенному прайсингу.

---

## 2. Компоненты слоя AI

| Компонент | Файл | Роль |
|---|---|---|
| `BaseAgent` | `backend/src/agents/base_agent.py` | Обёртка над `ChatOpenAI`: стриминг, история диалога, tools, callback'и токенов, статус агента |
| `AgentFactory` | `backend/src/agents/agent_factory.py` | Фабрика: маппинг `AgentType → OpenRouter model ID`, system prompts, создание main/sub-агентов |
| `TaskOrchestrator` | `backend/src/core/orchestrator/task_orchestrator.py` | Мульти-агентная координация: решение о делегировании, раунды обсуждения, синтез |
| `TokenTrackingCallback` | `backend/src/infrastructure/tracking/callback_handler.py` | LangChain `AsyncCallbackHandler`: извлекает token usage из ответов LLM (форматы OpenAI / Anthropic / Google) |
| `TokenTrackingManager` | `backend/src/infrastructure/tracking/token_manager.py` | In-memory агрегация usage по сессиям, моделям и агентам |
| `MODEL_PRICING_CONFIG` | `backend/src/core/token_models.py` | Прайсинг 9 моделей (per 1K токенов, context window) |

### Иерархия агентов

- **Main agent** (`main_orchestrator`, `AgentType.CLAUDE_MAIN` → `anthropic/claude-3.5-sonnet`,
  temperature 0.8) — единственная точка контакта с пользователем. Анализирует задачу,
  решает, нужна ли помощь, синтезирует финальный ответ.
- **Sub-agents** (`AgentType.CLAUDE_SUB` → `anthropic/claude-3-5-haiku`, `AgentType.GPT5` → `openai/gpt-4o`,
  temperature 0.7) — специализированные агенты, создаваемые фабрикой под конкретную подзадачу.
  С пользователем напрямую не общаются — только с оркестратором.

---

## 3. Жизненный цикл запроса к модели

### 3.1 Создание агента

```python
# backend/src/agents/agent_factory.py
agent = AgentFactory.create_main_agent(session_id=session_id)
# → MODEL_MAP[CLAUDE_MAIN] = "anthropic/claude-3.5-sonnet"
# → SYSTEM_PROMPTS[CLAUDE_MAIN] (роль оркестратора + описание web_search)
# → AgentConfig(agent_id="main_orchestrator", model=..., temperature=0.8, max_tokens=4096)
# → BaseAgent(config, session_id)
```

### 3.2 Ленивая инициализация модели

`ChatOpenAI` создаётся только при первом обращении и кэшируется (отдельно для streaming
и non-streaming вариантов). Ключ берётся из `SettingsService`: сначала БД
(таблица `app_settings`), затем переменные окружения.

### 3.3 Вызов модели

Два режима:

- `get_complete_response(messages)` → `chat_model.ainvoke(...)` — целый ответ строкой.
  Используется для служебных шагов (план делегирования).
- `stream_response(messages)` → `async for chunk in chat_model.astream(...)` — генератор
  `StreamChunk` по токенам. Используется для всего, что видит пользователь.

Сообщения передаются в OpenAI-формате `[{"role": "system"|"user"|"assistant", "content": str}]`
и конвертируются в объекты LangChain (`SystemMessage` / `HumanMessage` / `AIMessage`).

### 3.4 Поток событий до пользователя

`TaskOrchestrator.process_task()` — async-генератор словарей-событий:

1. `init` — присвоенный `conversationId`.
2. `agent_status` (thinking) — main agent анализирует задачу.
3. Если коллаборация включена: `_get_delegation_plan()` — non-streaming запрос к main
   agent, который обязан вернуть JSON вида
   `{"delegate": bool, "reasoning": str, "sub_queries": [{"agent_type", "query", "priority"}]}`.
4. `delegation` — список созданных суб-агентов.
5. `_run_agent_conversation()` — до 3 раундов (`max_conversation_rounds = 3`) обсуждения
   между суб-агентами; каждый агент видит весь контекст предыдущих раундов. События:
   `agent_thinking` → `agent_message_chunk` (по токенам) → `agent_message` (isComplete) →
   `conversation_round_complete`.
6. Синтез: `_prepare_synthesis_from_conversation()` собирает все раунды в один промпт,
   main agent стримит финальный ответ — события `stream` (по токенам) → `complete`.

События уходят клиенту по WebSocket (основной канал, поддерживает отмену через
`{type: "stop"}` → `orchestrator.cancel()`) или по SSE (`POST /api/task/stream`).
Финал каждой задачи — сохранение сообщений в PostgreSQL и логирование
`session_token_usage_summary` (токены, стоимость, разбивка по моделям и агентам).

---

## 4. Трекинг токенов и стоимости

- На каждый экземпляр `ChatOpenAI` вешается `TokenTrackingCallback`
  (`on_llm_end` извлекает usage из ответа; поддержаны форматы OpenAI, Anthropic, Google).
- `TokenTrackingManager` агрегирует записи `TokenUsage` по сессиям WS/REST
  **в памяти процесса** (данные теряются при рестарте — известное ограничение, см. `docs/04`).
- Стоимость считается по `MODEL_PRICING_CONFIG`: цена per 1K input/output токенов и
  размер контекстного окна для 9 моделей (OpenAI, Anthropic, Google, X.AI).
- API-аналитика: `GET /api/tokens/pricing`, `POST /api/tokens/calculate`,
  `POST /api/tokens/compare`, `GET /api/tokens/stats/...`.

---

## 5. Инструменты (tools) — текущий статус

Слой инструментов спроектирован полностью:

- `BaseTool` (ABC) генерирует OpenAI function-calling схему (`get_schema()`);
- `WebSearchTool` — поиск через DuckDuckGo (без ключа), Tavily или SerpAPI;
- `ToolRegistry` — регистрация/выполнение, схемы передаются в `ChatOpenAI(tools=...)`.

**Ограничение (важно):** схемы tools передаются модели, но фактическое выполнение
tool calls из ответа LLM в стриминг-цикле **не реализовано** — `BaseAgent.execute_tool()`
существует, но никем не вызывается автоматически (см. `docs/04_code_quality.md`).
Рабочий способ использования сейчас — прямой вызов из кода (см. пример в
`docs/08_code_examples.md`, раздел 5).

---

## 6. Надёжность и деградация

- Ошибка парсинга JSON плана делегирования → `{"delegate": false}` — задача выполняется
  без суб-агентов, сбоя пользователь не видит.
- Ошибка LLM в стриминге → финальный чанк `StreamChunk(content="Error: ...", metadata={"error": true})`,
  поток не падает.
- Невалидный `agent_type` от LLM → alias-маппинг (`gpt-4`, `gpt-4o`, `gpt4`, `gpt5` → `AgentType.GPT5`)
  или пропуск агента с логом ошибки.
- Отмена: флаг `is_cancelled` проверяется на каждом токене стриминга; клиент получает
  `cancelled` с `partialResponse`.
- PostgreSQL недоступен → приложение работает в degraded mode: ответы LLM идут, но
  история не сохраняется.

## 7. Известные несоответствия и долг

- `AgentType` enum (`claude-sonnet-4.5`, `claude-sonnet-3.5`, `gpt-5`) не совпадает с
  реальными model ID в `MODEL_MAP` (`claude-3.5-sonnet`, `claude-3-5-haiku`, `gpt-4o`) —
  это маркетинговые имена в UI, не технические ID.
- `_execute_sub_agents()` (параллельное выполнение) — мёртвый код; реальный путь —
  последовательный `_run_agent_conversation()`.
- `AgentFactory.QUORUM_MODELS` и выбор моделей в `QuorumSettings.tsx` определены, но
  оркестратор их не применяет (состав суб-агентов решает main agent через делегирование).
- Tool calling не доведён до автоматического выполнения (раздел 5).
- Токен-статистика хранится только в памяти.
