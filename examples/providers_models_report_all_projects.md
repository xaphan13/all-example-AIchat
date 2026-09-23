# Сводный отчёт по провайдерам и моделям AI: как проекты работают с нейросетями

> Дата: 30.08.2026
> Источники: `agents_docs/<проект>/07_*` (для AI-Chatbot — `10_models_and_providers.md`)
> + проверка фактического кода проектов.
> Формат: сравнительный обзор — как каждый проект общается с нейросетями, какие модели
> используются, какие провайдеры подключены фактически и какие можно подключить.

---

## 1. Главная мысль

**Де-факто стандартом во всех 6 проектах является OpenAI Chat Completions API.** Даже там, где провайдер — не OpenAI (GitHub Models, Groq, OpenRouter), общение с нейросетью идёт либо через OpenAI-совместимый формат (`AsyncOpenAI` + другой `base_url`, либо `httpx` POST на совместимый endpoint), либо через нативный SDK того же формата (Groq). Единственное исключение из «чистого OpenAI-протокола» — проект 4 (openai-responses-python-quickstart), использующий более новый **Responses API**.

Это означает: практически любой провайдер, предоставляющий OpenAI-совместимый endpoint (OpenRouter, Groq, vLLM, Ollama, LM Studio, LiteLLM, Together, DeepSeek и т.д.), подключается заменой `base_url` + API-ключа + имени модели. Провайдеры с собственными API (Anthropic Messages API, Google Gemini API, Azure OpenAI) требуют отдельного адаптера/клиента.

---

## 2. Сравнительная таблица провайдеров и моделей

| Критерий | AI-Chatbot | GroqStreamChain | LLM Council | OpenAI Responses Quickstart | Quorum | RAG Chatbot |
|---|---|---|---|---|---|---|
| **Провайдер (факт.)** | GitHub Models | Groq Cloud | OpenRouter | OpenAI | OpenRouter | OpenAI (или любой OpenAI-совместимый) |
| **API-контракт** | Chat Completions (OpenAI-compatible) | Chat Completions (нативный SDK `groq`) | Chat Completions (сырой `httpx` POST) | **Responses API** + Conversations/Files/Vector Stores/Audio | Chat Completions (через LangChain `ChatOpenAI`) | Chat Completions + Embeddings + HTTP rerank |
| **Клиент** | `openai.AsyncOpenAI` | `groq.Groq` | `httpx.AsyncClient` | `openai.AsyncOpenAI` | `langchain-openai.ChatOpenAI` | `openai.AsyncOpenAI` (шлюз `LLMGateway`) |
| **Секрет** | `GITHUB_TOKEN` | `GROQ_API_KEY` | `OPENROUTER_API_KEY` | `OPENAI_API_KEY` | `OPENROUTER_API_KEY` | `OPENAI_API_KEY` (+ `llm_api_key` в БД) |
| **Модели (факт.)** | `openai/gpt-4o` (захардкожено) | `MODEL_NAME` из `.env` (default `llama-3.1-8b-instant`) | 4 члена совета + председатель + `gemini-2.5-flash` (заголовки) | `RESPONSES_MODEL` (default `gpt-5-mini`) + `whisper-1` | main `anthropic/claude-3.5-sonnet`; sub `claude-3-5-haiku`, `openai/gpt-4o` | primary `gpt-5.2`, economy `gpt-4o-mini`, fallback `gpt-3.5-turbo`, embeddings `text-embedding-3-small` |
| **Где задаётся модель** | литерал в коде | `.env` | `backend/config.py` (списки) | `.env` + UI `/setup` | `AgentFactory.MODEL_MAP` | env → БД `app_config` → Admin API (на лету) |
| **Стриминг от модели** | нет | да (`stream=True`, чанки → WebSocket) | нет (SSE — только прогресс стадий) | да (`stream=True`, ~20 типов событий → SSE) | да (`astream`, по токенам → WS/SSE) | нет (`stream=True` не используется; SSE — псевдостриминг) |
| **Tool calling** | нет | нет | нет | да (7 типов инструментов) | спроектирован, но не выполняется автоматически | нет (JSON-контракты вместо tools) |
| **LLM-вызовов на запрос** | 1 | 1 | 4 + 4 + 1 + 1 (фон) | 1 + рестарты после tools | 1 (план) + N×раунды (до 3) + 1 (синтез) | до 8–10 (роли пайплайна) |
| **Мультиагентность** | нет | нет | мультимодельный совет | нет | да (оркестратор + sub-agents) | мультиролевой пайплайн (state machine) |
| **Fallback-модель** | нет | нет | graceful degradation (пропуск упавшей) | нет | нет | да (`[primary, fallback]` в шлюзе) |

---

## 3. Проект 1 — AI-Chatbot: GitHub Models

**Как работает:** один вызов `AsyncOpenAI` с `base_url="https://models.github.ai/inference/"` и ключом `GITHUB_TOKEN`. Модель `openai/gpt-4o` задана литералом в `app/services/chat.py`, без стриминга, без истории диалога.

```python
client = AsyncOpenAI(api_key=settings.GITHUB_TOKEN,
                     base_url="https://models.github.ai/inference/")
response = await client.chat.completions.create(model="openai/gpt-4o",
                                                messages=[{"role": "user", "content": message}])
```

**Что можно подключить:**
- Любой OpenAI-совместимый endpoint заменой `base_url`: OpenAI (`api.openai.com/v1`), Ollama (`localhost:11434/v1`), self-hosted vLLM и др.
- Azure OpenAI — только через отдельный клиент `AsyncAzureOpenAI` (deployment name + api_version).
- Anthropic и Google Gemini — **нужен отдельный адаптер**: у них собственные Messages/SDK-форматы, «совместимость» через пакет `openai` их не покрывает.

**Слабое место:** `model` и `base_url` захардкожены; в доке `10_models_and_providers.md` есть готовый план выноса в `LLM_BASE_URL` / `LLM_MODEL` / `LLM_TIMEOUT` в `app/core/config.py`.

---

## 4. Проект 2 — GroqStreamChain: Groq Cloud (нативный SDK)

**Как работает:** единственный runtime-канал — официальный пакет `groq` (`services/llm_service.py`). Синхронный `client.chat.completions.create(..., stream=True)` обёрнут в `asyncio.to_thread`, чанки (`chunk.choices[0].delta.content`) немедленно транслируются клиенту по WebSocket `WS /ws/chat` (фреймы `stream` / `stream_end`).

- Модель — любая, принимаемая Groq API, через `MODEL_NAME` в `.env` (default `llama-3.1-8b-instant`). Популярные: `llama-3.3-70b-versatile`, `openai/gpt-oss-120b`, `groq/compound` (managed-агент с веб-поиском).
- Клиент `langchain_groq.ChatGroq` инициализирован, но **не вызывается** — мёртвый код.
- Провайдер зашит жёстко: смена на другого провайдера = правка кода, а не конфига (техдолг `LLMProvider` из roadmap не реализован).

**Что можно подключить:** только модели внутри Groq без правки кода. Другие провайдеры — через реализацию интерфейса `LLMProvider` (план в `05_optimization_roadmap.md`).

**Известный баг:** `messages.insert(0, system_message)` мутирует список истории сессии — системный промпт накапливается с каждым ходом диалога.

---

## 5. Проект 3 — llm-council-karpathy: OpenRouter, совет из 4+1 моделей

**Как работает:** сырые HTTPS POST (`httpx.AsyncClient`) на `https://openrouter.ai/api/v1/chat/completions` — единственное место (`backend/openrouter.py`), откуда уходит запрос к LLM. Формат — OpenAI Chat Completions; системные промпты не используются, все инструкции вшиты в `role: "user"`.

Три стадии (`backend/council.py`):
1. **Stage 1** — 4 модели из `COUNCIL_MODELS` параллельно (`asyncio.gather`) отвечают на вопрос.
2. **Stage 2** — те же модели анонимно рецензируют ответы под метками `Response A/B/C/...`; рейтинг парсится регэкспом из секции `FINAL RANKING:`; агрегируется средний ранг («Street Cred»).
3. **Stage 3** — `CHAIRMAN_MODEL` синтезирует финальный ответ из всех ответов и рецензий.

Состав совета (`backend/config.py`): `openai/gpt-5.1`, `google/gemini-3-pro-preview`, `anthropic/claude-sonnet-4.5`, `x-ai/grok-4`; председатель — `google/gemini-3-pro-preview`; заголовки — `google/gemini-2.5-flash` (захардкожена в `council.py`).

**Что можно подключить:** любую модель из каталога OpenRouter (ID вида `vendor/model-name`) — просто редактированием списка в `config.py`. Ошибочный ID просто пропускается (graceful degradation). Прямые интеграции с OpenAI/Anthropic/Google API отсутствуют — потребуют доработки `openrouter.py`.

**Нюансы:** таймаут 120 с; пустой `content` не считается ошибкой; `label_to_model` и агрегированные рейтинги не персистятся.

---

## 6. Проект 4 — openai-responses-python-quickstart: OpenAI Responses API

**Как работает:** единственный провайдер — OpenAI, SDK `openai>=2.0` (`AsyncOpenAI`). Отличается от остальных проектов протоколом: **Responses API** (`responses.create`) вместо Chat Completions, состояние диалога хранится **на стороне OpenAI** (Conversations API — сервер передаёт только `conversation_id`).

Задействованные API OpenAI: `responses.create` (стриминг), `conversations.*` (история), `files.*` (vision), `vector_stores.*` (file search), `containers.*` (code interpreter), `audio.transcriptions` (Whisper `whisper-1`).

- Модель — `RESPONSES_MODEL` из `.env` (default `gpt-5-mini`), выбирается через UI `/setup` из захардкоженного списка из 19 моделей (gpt-4.x, gpt-5.x, o1/o3/o4, gpt-oss). Конфиг перечитывается на каждый запрос — смена без рестарта.
- **Единственный проект с полноценным tool calling**: code interpreter, file search, custom functions (JSON Schema, параллельное выполнение через `asyncio.gather`), MCP с approval-флоу, web search, computer use (Playwright), image generation (заявлена, но README отмечает её неподдерживаемой — считать расхождением).
- Стриминг: SSE, state-machine `iterate_stream()` обрабатывает ~20 типов событий Responses API; после выполнения инструментов поток рестартуется рекурсивно.

**Что можно подключить:** не-OpenAI модели — только замена `AsyncOpenAI` и адаптация `iterate_stream()` под формат событий другого провайдера. Точки расширения: `ComputerSession` (замена Playwright), custom functions (любые внешние API), MCP-серверы.

---

## 7. Проект 5 — Quorum: OpenRouter через LangChain, мультиагентность

**Как работает:** LLM-слой — `langchain-openai.ChatOpenAI` с `base_url`, переключённым на OpenRouter (`backend/src/agents/base_agent.py`). Всё асинхронно: `ainvoke` (целый ответ — служебные шаги) и `astream` (поток по токенам — всё, что видит пользователь). На каждый вызов повешен `TokenTrackingCallback` — трекинг токенов и стоимости по прайсингу `MODEL_PRICING_CONFIG` (in-memory, теряется при рестарте).

Иерархия агентов (`AgentFactory.MODEL_MAP`):
- **Main agent** (`anthropic/claude-3.5-sonnet`, temp 0.8) — анализ задачи, решение о делегировании (JSON-план), синтез финала.
- **Sub-agents** (`anthropic/claude-3-5-haiku`, `openai/gpt-4o`, temp 0.7) — до 3 раундов конференции между собой, затем синтез main-агентом.

Транспорт к пользователю: WebSocket (основной, с отменой через `{type:"stop"}`) + SSE fallback (`POST /api/task/stream`).

**Что можно подключить:** любую модель OpenRouter через правку `MODEL_MAP`; один ключ открывает Anthropic, OpenAI, Google, X.AI и ~300 других вендоров. Прямые API вендоров — потребуют замены `ChatOpenAI` на соответствующие LangChain-обёртки.

**Известные несоответствия:** `AgentType` enum не совпадает с реальными model ID (маркетинговые имена в UI); параллельное выполнение sub-agents (`_execute_sub_agents`) — мёртвый код, реально всё последовательно; tool-calling спроектирован (`BaseTool`, `ToolRegistry`, `WebSearchTool`), но автоматическое выполнение вызовов инструментов из ответа LLM не реализовано.

---

## 8. Проект 6 — rag-knowledge-base-chatbot: OpenAI-совместимый шлюз, мультиролевой пайплайн

**Как работает:** все обращения к нейросетям — через единый абстрактный шлюз `LLMGateway` (`app/services/llm_gateway.py`, реализация `OpenAIGateway` на `openai.AsyncOpenAI`). До 8–10 LLM-вызовов на один запрос пользователя: 13 специализированных ролей (Normalizer, Query Rewriter, Evidence Selector/Evaluator/Quality Gate, Decision Router, Generator, Self-Critic, Final Polish и др.), каждая со своим системным промптом и **строгим JSON-контрактом** ответа. Координация — детерминированный state machine `Orchestrator` (`UNDERSTAND → RETRIEVE → ASSESS_EVIDENCE → DECIDE → GENERATE → VERIFY`).

Три канала AI:
1. Chat Completions — все текстовые роли.
2. Embeddings API — `text-embedding-3-small` (1536 dims) для гибридного поиска (BM25/OpenSearch + Qdrant + RRF).
3. HTTP rerank — локальный cross-encoder `ms-marco-MiniLM-L-6-v2` или Cohere `rerank-multilingual-v3.0`.

**Маршрутизация моделей:** primary `gpt-5.2` (генерация, самокритик), economy `gpt-4o-mini` (остальные ~10 ролей), fallback `gpt-3.5-turbo` (цепочка `[primary, fallback]` внутри одного вызова). Task-aware routing и точечные переопределения модели на роль.

**Конфигурация — трёхуровневая, без редеплоя:** env → таблица `app_config` в PostgreSQL (кэш 60 с) → Admin API / Settings UI (`GET/PUT /v1/admin/config/llm`). Модель, ключ и `base_url` меняются на лету.

**Что можно подключить:** любой OpenAI-совместимый endpoint через `OPENAI_BASE_URL` / `llm_base_url` в БД — OpenRouter, vLLM, LM Studio, Ollama, LiteLLM, Azure-совместимые шлюзы. Провайдер `custom` объявлен в конфиге, но фабрика бросает `ValueError` — это незаполненная точка расширения (`get_llm_gateway()`).

**Нюансы:** `stream=True` не используется — SSE-эндпоинт отдаёт «псевдостриминг» (готовый ответ кусками по 100 символов); для `o1*`/`gpt-5*` автоматически подставляется `max_completion_tokens`; Redis-кэш ответов (`sha256(messages+model+temperature)`, TTL 3600 с); tool calling отсутствует принципиально (JSON-контракты вместо tools).

---

## 9. Какие провайдеры возможно подключать (сводно)

### Подключается «малой кровью» (OpenAI-совместимый endpoint)

| Провайдер | Способ | Проекты, где это возможно |
|---|---|---|
| OpenAI | `base_url` → `api.openai.com/v1` | все, кроме 3 и 5 (там — через OpenRouter) |
| OpenRouter | один ключ → сотни моделей (OpenAI/Anthropic/Google/xAI/Meta/DeepSeek/Mistral/Qwen…) | фактически используется в 3 и 5; подключаем в 1 и 6 |
| Groq | свой SDK или OpenAI-compatible endpoint | фактически в 2; совместимый endpoint — в 1 и 6 |
| Ollama (локально) | `base_url` → `localhost:11434/v1` | 1 и 6 напрямую; 4 — с адаптацией |
| vLLM / LM Studio / LiteLLM / Together / DeepSeek | любой OpenAI-совместимый сервер | 1 и 6 напрямую |
| GitHub Models | `base_url` → `models.github.ai/inference/` | фактически в 1; подключаем в 6 |

### Требует отдельного адаптера (собственный API)

| Провайдер | Причина | Где упоминается |
|---|---|---|
| Anthropic | собственный Messages API, формат ролей и ответов | 1 (10_models), 4, 6 |
| Google Gemini | собственный SDK, content parts, safety settings | 1 (10_models), 4, 6 |
| Azure OpenAI | особая схема: `AsyncAzureOpenAI`, deployment name, api_version | 1 (10_models) |
| Cohere | отдельный Rerank API (не чат) | фактически в 6 (реранкер) |

### Ключевое наблюдение

Проекты 3 и 5 (OpenRouter) и 6 (`base_url` в БД) архитектурно готовы к наибольшей гибкости провайдеров. Проект 6 — единственный, где провайдер, модель и ключ меняются **без редеплоя** через админку. Проекты 1, 2 и 4 зашиты на одного провайдера на уровне кода.

---

## 10. Сравнение «глубины» работы с нейросетями

От простого к сложному:

1. **AI-Chatbot** — 1 запрос → 1 ответ, без истории, без стриминга. Эталон минимальной интеграции.
2. **GroqStreamChain** — 1 запрос → 1 ответ, но с настоящим токен-стримингом через WebSocket и историей сессии в памяти.
3. **LLM Council** — 10 вызовов на запрос (4+4+1+1), кооперация моделей через промпты, анонимное ранжирование; стриминга токенов нет.
4. **OpenAI Responses Quickstart** — 1 вызов + рекурсивные рестарты после инструментов; полноценный tool-calling цикл, состояние на стороне провайдера, мультимодальность (vision + Whisper).
5. **Quorum** — оркестратор создаёт суб-агентов с разными моделями, до 3 раундов обсуждения, синтез; токен-стриминг, трекинг стоимости; tools спроектированы, но не выполняются автоматически.
6. **RAG Chatbot** — до 8–10 вызовов разных ролей на запрос под управлением детерминированного state machine, JSON-контракты, fallback-модели, кэширование, task-aware маршрутизация моделей, embeddings + rerank; но без tool calling и без настоящего токен-стриминга.

---

## 11. Итог

- **Провайдеры:** GitHub Models, Groq, OpenRouter (×2), OpenAI (×2). Ни один проект не имеет абстракции над несколькими провайдерами одновременно, кроме RAG Chatbot (шлюз `LLMGateway` + конфиг в БД) — и то с одним активным типом шлюза.
- **Модели:** от единственной захардкоженной (`openai/gpt-4o`) до настраиваемых списков (совет из 4, 19 моделей в UI, 3 уровня ролей + fallback).
- **Протокол:** OpenAI Chat Completions везде, кроме проекта 4 (Responses API). Это делает почти любой современный провайдер подключаемым через `base_url`.
- **Расширяемость:** лучшие точки расширения — `LLMGateway` (проект 6), `AgentFactory.MODEL_MAP` (проект 5), `COUNCIL_MODELS` (проект 3). Худшая — проекты 1 и 2, где провайдер вшит в код литералом.

### Связанные документы

| Проект | Детальный отчёт |
|---|---|
| AI-Chatbot | `../agents_docs/AI-Chatbot/10_models_and_providers.md` |
| GroqStreamChain | `../agents_docs/GroqStreamChain/07_ai_models_report.md` |
| LLM Council | `../agents_docs/llm-council-karpathy/07_ai_report.md` |
| OpenAI Responses Quickstart | `../agents_docs/openai-responses-python-quickstart/07_ai_models_report.md` |
| Quorum | `../agents_docs/Quorum/07_ai_models_report.md` |
| RAG Chatbot | `../agents_docs/rag-knowledge-base-chatbot/07_ai_models_report.md` (+ `08_ai_code_examples.md`) |
