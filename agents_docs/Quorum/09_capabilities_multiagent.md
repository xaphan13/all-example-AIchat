# 09 — Возможности и мультиагентный режим

> Что умеет приложение NoOversight / Quorum и как устроена коллаборация нескольких
> AI-агентов. Версия анализа: август 2026.

---

## 1. Возможности приложения

### 1.1 Общение с LLM

- **Чат с AI в двух режимах** — Solo (один агент) и Quorum (мультиагентная коллаборация);
  переключатель `ModeSelector` в шапке интерфейса.
- **Потоковые ответы токен за токеном** — генерация отображается в реальном времени,
  без ожидания полного ответа.
- **Контекст диалога** — история сообщений учитывается в последующих запросах:
  хранится в PostgreSQL и в памяти оркестратора на время WS-сессии.
- **Отмена генерации** — кнопка stop прерывает стриминг на любом токене, частичный
  ответ сохраняется.
- **Markdown-рендеринг ответов** — заголовки, списки, таблицы, блоки кода (GFM).

### 1.2 Управление диалогами

- История диалогов в левой панели с поиском, «избранным» и загрузкой прошлых бесед.
- Персистентность в PostgreSQL: диалоги, сообщения (user / assistant / agent-to-agent),
  метаданные, токены и стоимость по каждому сообщению.
- Переименование и удаление диалогов; экспорт диалога в PDF.

### 1.3 Мониторинг агентов и стоимости

- **AgentPanel** — правая панель с карточками активных агентов: статус
  (idle / thinking / responding / complete / error), текущая задача, прогресс.
- **AgentConversation** — отображение раундов обсуждения между агентами: видно, кто
  и что сказал в каждом раунде.
- **Трекинг токенов и стоимости** — расход input/output токенов и стоимость в USD
  по каждому агенту, модели и сессии; UI-компоненты `TokenUsageDisplay` и
  `CostCalculator` (сравнение цен моделей до отправки запроса).
- API-аналитика: `/api/tokens/pricing`, `/api/tokens/calculate`, `/api/tokens/compare`,
  `/api/tokens/stats/...`.

### 1.4 Инструменты и поиск

- **Web search**: DuckDuckGo (без ключа), Tavily, SerpAPI — через `WebSearchTool`
  (`backend/examples/web_search_example.py` — рабочая демонстрация).
- Отображение результатов поиска в UI (`ToolUsageDisplay`, `AgentToolDisplay`).
- Статус: tool schemas передаются модели, но автоматический function calling пока не
  доведён до конца — см. раздел 7 в `docs/07_ai_models_report.md`.

### 1.5 Знаниевая база

- Embeddings сообщений через OpenAI (`text-embedding-3-small`, 1536 измерений).
- Векторный поиск по диалогам (pgvector, IVFFlat, cosine similarity).

### 1.6 Настройки

- API-ключ OpenRouter через UI (хранится в БД) или через `.env`; валидация ключа.
- Выбор моделей для Quorum-режима и числа раундов (`QuorumSettings`).
- Тема оформления, уведомления, уровень логирования.

---

## 2. Мультиагентное использование

**Да, мультиагентность — ядро продукта.** Реализована в `TaskOrchestrator`
(`backend/src/core/orchestrator/task_orchestrator.py`). Включается флагом
`enable_collaboration: true` в `TaskRequest` (режим Quorum в UI).

### 2.1 Схема работы

```
Пользователь
     │
     ▼
┌──────────────────────────────────────────────────────────┐
│ 1. Main Agent (Claude 3.5 Sonnet) анализирует задачу     │
│ 2. Возвращает JSON-план: делегировать или нет, кому, что  │
└──────────────────────┬───────────────────────────────────┘
                       │ delegate = true
                       ▼
┌──────────────────────────────────────────────────────────┐
│ 3. AgentFactory создаёт sub-агентов по sub_queries       │
│    (Claude 3.5 Haiku для анализа, GPT-4o для креатива)   │
└──────────────────────┬───────────────────────────────────┘
                       ▼
┌──────────────────────────────────────────────────────────┐
│ 4. Конференция: до 3 раундов обсуждения                  │
│    — агенты отвечают последовательно внутри раунда       │
│    — каждый видит весь контекст предыдущих раундов       │
│    — могут соглашаться, спорить, уточнять друг друга     │
└──────────────────────┬───────────────────────────────────┘
                       ▼
┌──────────────────────────────────────────────────────────┐
│ 5. Main Agent синтезирует финальный ответ из обсуждения  │
│    → пользователь получает единый взвешенный ответ       │
└──────────────────────────────────────────────────────────┘
```

### 2.2 Протокол делегирования

Main agent обязан ответить строго JSON (`task_orchestrator.py:347-371`):

```json
{
  "delegate": true,
  "reasoning": "почему нужна помощь",
  "sub_queries": [
    { "agent_type": "claude-sonnet-3.5", "query": "конкретный вопрос", "priority": 1 },
    { "agent_type": "gpt-5", "query": "второй вопрос", "priority": 2 }
  ]
}
```

Допустимые `agent_type`: `"claude-sonnet-3.5"` и `"gpt-5"` (есть alias-фолбэк:
`gpt-4`, `gpt-4o`, `gpt4`, `gpt5` → `gpt-5`). Максимум суб-агентов задаётся
клиентом: `max_sub_agents` (по умолчанию 3).

### 2.3 Раунды обсуждения

- Раундов: до 3 (`max_conversation_rounds = 3`, захардкожено).
- Раунд 1 — первичный анализ каждого агента; раунды 2..3 — реакция на коллег:
  согласие/спор, дополнения, уточнения (`_prepare_conversation_prompt`).
- После каждого раунда контекст накапливается в `conversation_context` и подаётся
  следующему раунду целиком.
- Каждое высказывание стримится по токенам в UI (`agent_message_chunk`) и сохраняется
  в БД как сообщение с `message_type = "agent_conversation"`.

### 2.4 Что видит пользователь

Все стадии отражаются событиями: `delegation` (кто привлечён и зачем),
`agent_thinking`, `agent_message_chunk`, `agent_message`, `conversation_round_complete`
и финальный `stream`/`complete`. UI рисует карточки агентов и ленту их диалога
в правой панели.

### 2.5 Ограничения текущей реализации

- Суб-агенты внутри раунда работают **последовательно, а не параллельно**
  (метод `_execute_sub_agents()` с `asyncio.gather` существует, но не используется —
  см. `docs/04`).
- Состав суб-агентов сейчас выбирает main agent текстовым решением; явный выбор
  моделей в `QuorumSettings` задекларирован, но оркестратор его не применяет.
- «Правильное» количество раундов не вычисляется — всегда выполняются все 3 раунда.

---

## 3. Формат общения с нейросетями

### 3.1 Внутри backend: OpenAI chat completions

Запросы к моделям — стандартные chat completions через OpenRouter:

- endpoint: `POST https://openrouter.ai/api/v1/chat/completions` (через LangChain);
- тело: `{ "model": "anthropic/claude-3.5-sonnet", "messages": [...], "temperature": 0.7, "max_tokens": 4096, "stream": true|false }`;
- сообщения: `[{"role": "system"|"user"|"assistant", "content": "..."}]`;
- system prompt задаёт роль агента (оркестратор, аналитик, креативщик) и описание tools.

### 3.2 Между frontend и backend: два канала

**WebSocket `/ws`** — основной. Клиент отправляет:

```json
{ "type": "task", "task": { "message": "...", "conversationId": "conv_...", "maxSubAgents": 3, "enableCollaboration": true } }
{ "type": "stop", "conversationId": "conv_..." }
{ "type": "ping" }
```

Сервер стримит события: `connected`, `init`, `agent_status`, `delegation`,
`agent_thinking`, `agent_message_chunk`, `agent_message`, `conversation_round_complete`,
`stream`, `complete`, `cancelled`, `error`, `pong`.

**SSE `POST /api/task/stream`** — fallback. Ответ — поток `data: {json}\n\n`,
завершается событием `stream_end`.

Полный справочник типов событий — в `docs/03_execution_flow.md`, раздел 3.2.

### 3.3 Как клиент рисует поток

Все события проходят единый обработчик `handleStreamEvent` в Zustand store
(event sourcing): токены дописываются в текущее сообщение, статусы обновляют карточки
агентов, `complete` фиксирует диалог в истории.

---

## 4. Модели и провайдеры

### 4.1 Провайдер доступа

**OpenRouter** — единая точка доступа ко всем LLM (OpenAI-совместимый API).
Один ключ `OPENROUTER_API_KEY` → 300+ моделей без отдельных интеграций.
Дополнительно: OpenAI API используется для embeddings, DuckDuckGo/Tavily/SerpAPI —
для веб-поиска.

### 4.2 Модели, используемые в коде

| Роль | OpenRouter model ID | Назначение |
|---|---|---|
| Main orchestrator | `anthropic/claude-3.5-sonnet` | Анализ задачи, делегирование, синтез финального ответа |
| Sub-agent | `anthropic/claude-3-5-haiku` | Быстрый детальный анализ |
| Sub-agent | `openai/gpt-4o` | Креативные и аналитические задачи |

Список «Quorum-моделей» (задекларирован в `AgentFactory.QUORUM_MODELS` и UI
`QuorumSettings.tsx`): Claude 3.5 Haiku, Gemini 2.0 Flash, Grok Beta, GPT-4o —
план на расширение состава суб-агентов (см. ограничения в разделе 2.5).

### 4.3 Модели с прайсингом (`MODEL_PRICING_CONFIG`)

| Модель | Input $/1M tok | Output $/1M tok | Context |
|---|---:|---:|---:|
| `openai/gpt-4o` | 2.50 | 10.00 | 128K |
| `openai/gpt-4o-mini` | 0.15 | 0.60 | 128K |
| `openai/gpt-4-turbo` | 10.00 | 30.00 | 128K |
| `anthropic/claude-3.5-sonnet` | 3.00 | 15.00 | 200K |
| `anthropic/claude-3-5-haiku` | 1.00 | 5.00 | 200K |
| `anthropic/claude-3-opus` | 15.00 | 75.00 | 200K |
| `google/gemini-pro` | 0.125 | 0.375 | 128K |
| `google/gemini-2.0-flash-exp` | 0 (эксперим.) | 0 (эксперим.) | 1M |
| `x-ai/grok-beta` | 5.00 | 15.00 | 128K |

### 4.4 Как добавить любую другую модель

Поскольку доступ идёт через OpenRouter, технически поддерживается любая модель из
их каталога (Mistral, Llama, DeepSeek, Qwen и т.д.). Достаточно:

1. Добавить значение в `AgentType` (`backend/src/core/models.py`).
2. Добавить маппинг в `AgentFactory.MODEL_MAP` (`backend/src/agents/agent_factory.py`)
   в формате `provider/model-name`.
3. (Опционально) дописать system prompt в `SYSTEM_PROMPTS` и прайсинг в
   `MODEL_PRICING_CONFIG` — без записи в прайсинге модель работает, но её стоимость
   будет нулевой в аналитике.

Модель определяется провайдером в префиксе ID (`anthropic/…`, `openai/…`, `google/…`,
`x-ai/…`) — метод `BaseAgent._get_provider_name()` извлекает его для логов.
