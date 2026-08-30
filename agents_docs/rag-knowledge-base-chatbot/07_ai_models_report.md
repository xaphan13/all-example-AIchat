# 07 — Отчёт: работа приложения с моделями AI

> Дата отчёта: 2026-08-15. Отчёт основан на фактическом коде репозитория (`app/services/`, `app/search/`, `app/core/`, `app/api/`). Аннотированные примеры кода вынесены в отдельный файл: [08_ai_code_examples.md](./08_ai_code_examples.md).

## 1. Резюме

Приложение **Auto Reply Chatbot | Support AI Assistant** — enterprise RAG-чатбот. Все обращения к нейросетям идут через единый абстрактный шлюз `LLMGateway` (`app/services/llm_gateway.py`), реализующий протокол OpenAI Chat Completions. Внутри одного запроса приложение делает **до 8–10 отдельных LLM-вызовов разных специализированных ролей** (нормализация запроса, оценка доказательств, генерация, самокритика и т.д.) — это мультиролевая LLM-архитектура, координируемая детерминированным оркестратором.

Ключевые факты:

| Аспект | Значение |
|---|---|
| Протокол общения с LLM | OpenAI Chat Completions API (async), JSON-only ответы |
| Провайдер LLM | OpenAI и любой OpenAI-совместимый endpoint (через `base_url`) |
| Модели по умолчанию | primary `gpt-5.2`, economy `gpt-4o-mini`, fallback `gpt-3.5-turbo` |
| Embeddings | OpenAI `text-embedding-3-small` (1536 dims) |
| Реранкеры | local (cross-encoder), Cohere, no-op |
| Конфигурация моделей | env → БД (`app_config`) → Admin API/Settings UI, без редеплоя |
| Мультиагентность | мультиролевой пайплайн внутри; интеграция как «агент-инструмент» снаружи; нативного tool-calling нет |

---

## 2. В каком виде происходит общение с нейросетями

### 2.1 Транспорт и протокол

Все LLM-вызовы проходят через `OpenAIGateway` (`app/services/llm_gateway.py:51`), использующий официальный async-клиент `openai.AsyncOpenAI`. Это стандартный HTTPS-вызов `POST /chat/completions` в формате OpenAI:

```
messages = [
  {"role": "system", "content": "<системный промпт роли>"},
  {"role": "user",   "content": "<контекст истории, если есть>"},
  ...
  {"role": "user",   "content": "<запрос + доказательства/параметры>"}
]
```

Отдельные каналы взаимодействия с AI:

1. **Chat Completions** — все текстовые роли пайплайна (`llm.chat(...)`).
2. **Embeddings API** — `embeddings.create(model, input)` для векторизации при индексации и поиске (`app/search/embeddings.py:31`).
3. **HTTP rerank** — локальный cross-encoder-сервис или Cohere Rerank API; это не чат, а `POST` с `{query, documents, top_k}` (`app/search/reranker.py`).

### 2.2 Формат сообщений

- **System prompt** — многослойный: `Core rules` (непереопределяемые: только evidence, цитирование, JSON-вывод) + `Domain` (пресеты `support` | `legal` | `generic`) + `Custom rules` из БД (`app/services/branding_config.py:123`, `_build_layered_prompt`).
- **Каждая роль имеет собственный системный промпт**: нормализатор (`NORMALIZER_SYSTEM_PROMPT`, `app/services/normalizer.py:180`), генератор, самокритик (`SELF_CRITIC_PROMPT`, `app/services/self_critic.py:18`), reasoning prepass и др.
- В фазе генерации в user-сообщение подкладываются: вопрос, блок evidence (чанки из базы знаний), история диалога, опциональный внутренний reasoning-план (`app/services/phases/generate.py`).

### 2.3 Формат ответа: строго структурированный JSON

Приложение не использует свободный текст от модели. Каждая роль обязана вернуть **JSON по заданной схеме**; код парсит его и санитизирует:

- Генерация ответа — схема `{decision, answer, followup_questions, citations, confidence}` (`OUTPUT_SCHEMA`, `app/services/branding_config.py`); парсинг с обрезкой markdown-ограждений и fallback на невалидном JSON (`parse_llm_response`, `app/services/answer_utils.py:309`).
- Нормализатор — большая схема `QuerySpec` (intent, evidence_families, retrieval_profile, гипотезы, перефразировки); все значения проходят allow-list-коерцию (`app/services/normalizer.py`).
- Самокритик — `{pass, issues, suggested_fix}`.

Т.е. общение с нейросетями — «запрос сообщениями → JSON-контракт → типизированный dataclass» без function/tool calling: модель не вызывает инструменты, её вывод всегда интерпретируется кодом.

### 2.4 Параметры, кэширование, отказоустойчивость

| Механизм | Реализация |
|---|---|
| `temperature` | по умолчанию `0.0` (`llm_temperature`), у ролей свои значения (нормализатор `0.0`, branding `0.2`) |
| Лимит токенов | `max_tokens`; для моделей `o1*`/`gpt-5*` автоматически `max_completion_tokens` (`llm_gateway.py:91`) |
| Fallback модели | цепочка `[primary, fallback]` в одном вызове (`llm_gateway.py:98`) |
| Кэш ответов | Redis, ключ `llm_cache:{sha256(messages+model+temperature)}`, TTL 3600s (`llm_gateway.py:176`) |
| Prompt caching OpenAI | `prompt_cache_key`, `prompt_cache_retention` (`24h` / `in_memory`) |
| Таймаут/ретраи | `llm_timeout_seconds=60`, `llm_retry_attempts=2` |
| Метрики | счётчики запросов/токенов/оценки стоимости, trace использования (`app/core/metrics.py`) |

### 2.5 Стриминг

`POST /v1/conversations/{id}/messages:stream` (`app/api/routes/conversations.py:294`) — SSE. Важно: это **псевдопоток на уровне API** — сначала пайплайн полностью отрабатывает, затем готовый ответ раздаётся чанками по 100 символов + события `citations` и `done`. Токен-стриминга самой модели нет (SDK вызывается без `stream=True`).

---

## 3. Какие модели и провайдеры можно использовать

### 3.1 Провайдеры

| Подсистема | Заявлено в config | Реализовано фабрикой |
|---|---|---|
| LLM (chat) | `openai`, `custom` (`app/core/config.py:82`) | `openai` → `OpenAIGateway`; `custom` объявлен, но фабрика бросает `ValueError` — это точка расширения (`llm_gateway.py:225`) |
| Embeddings | `openai`, `custom` (`config.py:75`) | `openai` → `OpenAIEmbeddingProvider` |
| Реранкер | `local`, `cohere`, `custom` | все три: локальный HTTP cross-encoder, `CohereRerankerProvider`, `IdentityRerankerProvider` (no-op) |

**Практический вывод:** напрямую поддерживается OpenAI, но клиент инициализируется с переопределяемым `base_url` (`OPENAI_BASE_URL` / ключ `llm_base_url` в БД), поэтому работает **любой OpenAI-совместимый endpoint**: OpenRouter, vLLM, LM Studio, Ollama, LiteLLM, Azure-совместимые шлюзы и т.п. — при условии поддержки `/chat/completions` (и `/embeddings`, если используются вектора). API-ключ тоже переопределяется (`llm_api_key`).

### 3.2 Модели и маршрутизация по задачам

Модели по умолчанию (`app/core/config.py`, `.env.example`):

| Роль | Модель по умолчанию | Где задаётся |
|---|---|---|
| Primary (генерация, самокритик) | `gpt-5.2` | `LLM_MODEL` / ключ `llm_model` в БД |
| Economy (нормализатор, decision router, качество evidence, polish и др.) | `gpt-4o-mini` | `LLM_MODEL_ECONOMY` / ключ в БД |
| Fallback при ошибке primary | `gpt-3.5-turbo` | `LLM_FALLBACK_MODEL` / ключ в БД |
| Embeddings | `text-embedding-3-small`, 1536 dims | `EMBEDDING_MODEL`, `EMBEDDING_DIMENSIONS` |
| Локальный реранкер | `cross-encoder/ms-marco-MiniLM-L-6-v2` | `RERANKER_MODEL` |
| Cohere реранкер | `rerank-multilingual-v3.0` | жёстко в `reranker.py:73` |

Task-aware маршрутизация (`app/services/model_router.py:18`): при включённом `llm_task_aware_routing_enabled` критичные задачи (`generate`, `self_critic`) получают primary-модель, остальные 10 ролей — economy. Отдельные роли имеют точечные переопределения модели: `NORMALIZER_LLM_MODEL`, `DECISION_ROUTER_LLM_MODEL`, `EVIDENCE_EVALUATOR_LLM_MODEL`, `CONVERSATION_RELEVANCE_CHECK_MODEL`.

Поддерживаются модели семейства `o1*`/`gpt-5*` (для них автоматически используется параметр `max_completion_tokens`). Конкретная строка модели передаётся в API как есть — можно указать любую модель, доступную вашему провайдеру/endpoint'у.

### 3.3 Трёхуровневая конфигурация

1. **Env** (`Settings`, `app/core/config.py`) — базовые значения.
2. **БД** (таблица `app_config`, ключи `llm_model`, `llm_fallback_model`, `llm_api_key`, `llm_base_url`) — переопределяет env; кэш 60s, обновление на старте и при изменении (`app/services/llm_config.py`).
3. **Admin API / Settings UI** — `GET/PUT /v1/admin/config/llm`, `/config/archi`, `/config/prompt` и др. (`app/api/routes/admin.py:421+`): смена модели, провайдера, ключа и feature flags **на лету, без редеплоя**.

Feature flags, управляющие LLM-ролями: `evidence_quality_use_llm`, `evidence_quality_llm_v2`, `self_critic_enabled`, `final_polish_enabled`, `doc_type_classifier_enabled`, `decision_router_use_llm`, `query_rewriter_use_llm`, `evidence_selector_use_llm`, `normalizer_use_llm`, `llm_task_aware_routing_enabled`, `debug_llm_calls` и др.

---

## 4. Какие возможности предлагает приложение

### Пользовательские / API

- Многодиалоговый RAG-чат с историей: `POST /v1/conversations/{id}/messages` (синхронно) и `messages:stream` (SSE).
- **Stateless-генерация ответа для внешних платформ** `POST /v1/reply/generate` — для тикет-систем (WHMCS, Zendesk), livechat: запрос → ответ без создания диалога (`app/api/routes/reply.py`).
- Структурированный ответ: текст, `decision` (`PASS`/`ASK_USER`/`ESCALATE`), `confidence`, follow-up вопросы, источники-citations (chunk_id, URL, тип документа).
- **Эскалация на человека** (ESCALATE) и уточняющие вопросы (ASK_USER) — встроенные точки handoff.
- Guardrails: проверка на prompt-injection и санитизация ввода (`app/core/guardrails.py`), rate limiting, WAF-gateway middleware.

### База знаний

- Ingestion документов: загрузка, fetch URL, crawl сайтов — асинхронно через Celery (`worker/tasks.py`), сырьё в MinIO.
- Импорт/краул тикетов WHMCS как обучающих диалогов.
- Гибридный поиск: BM25 (OpenSearch) + вектора (Qdrant) + RRF-фузия + реранкер + LLM-отбор evidence.

### Администрирование

- React admin panel: управление LLM-конфигом, промптами (Core/Domain/Custom), intents, doc types, брендингом.
- Автогенерация брендинга/промпта из содержимого сайта через LLM (`branding_auto_generator.py`).
- Offline evaluation на golden set (`app/services/offline_eval.py`, `scripts/build_offline_eval_golden_set.py`).
- Dashboard-метрики, управление тикетами с approval-процессом.

### Наблюдаемость

- Prometheus-метрики LLM: запросы, токены, оценка стоимости (`app/core/metrics.py`).
- `flow_debug` payload в каждом ответе: стадии пайплайна, evidence, расход моделей.
- Режим `debug_llm_calls` — полная запись всех LLM-вызовов (промпты/ответы/стоимость) по запросу.

---

## 5. Возможно ли мультиагентное использование

### 5.1 Что уже есть: мультиролевой LLM-пайплайн

Фактически приложение уже построено как **комитет специализированных LLM-ролей** (прообраз мультиагентной системы), где у каждой роли свой промпт, своя модель и свой JSON-контракт:

| Роль | Назначение | Класс |
|---|---|---|
| Normalizer | понимание запроса, intent, план поиска | `normalizer.py` |
| Query Rewriter | перефразировки для поиска | `query_rewriter.py` |
| Evidence Selector | отбор чанков под требования | `evidence_selector.py` |
| Evidence Evaluator | оценка релевантности evidence | `evidence_evaluator.py` |
| Evidence Quality Gate | «достаточно ли доказательств» (pass/fail) | `evidence_quality.py` |
| Decision Router | выбор режима ответа | `decision_router.py` |
| Relevance Check | нужна ли история диалога | `phases/relevance_check.py` |
| Reasoning prepass | внутренний план перед генерацией | `phases/generate.py` |
| Generator | итоговый ответ с цитатами | `phases/generate.py` |
| Self-Critic | проверка grounding/полноты, регенерация при провале | `self_critic.py` |
| Final Polish | финальная стилизация | `final_polish.py` |
| Doc Type Classifier | классификация документов при ingestion | `doc_type_classifier.py` |
| Branding Generator | извлечение бренда/промпта из сайта | `branding_auto_generator.py` |

Координация — **детерминированный state machine** `Orchestrator` (`app/services/orchestrator.py`): UNDERSTAND → RETRIEVE → ASSESS → DECIDE → GENERATE → VERIFY с петлями повторов. Это сознательный проектный принцип («LLM is the orchestrator внутри роли, но не управляет потоком»): роли LLM принимают содержательные решения (intent, качество evidence, стратегия повтора), а переходы состояний — кодовые.

### 5.2 Использование как агента во внешних системах

Приложение **можно встроить в мультиагентную систему как готового «агента-эксперта по базе знаний»**:

- `POST /v1/reply/generate` — stateless, one-shot, идеален как tool/функция для LangGraph, CrewAI, AutoGen, MCP-шлюза: другие агенты делегируют ему вопросы по базе знаний и получают структурированный JSON (ответ + источники + confidence + decision).
- `ESCALATE` / `ASK_USER` — готовые точки передачи управления человеку или другому агенту-супервизору.
- Аутентификация API-ключами/JWT позволяет раздавать доступ разным агентам.

### 5.3 Что потребуется для нативной мультиагентности

Сегодняшние ограничения (подтверждено по коду):

- **Нет tool/function calling** — модель не вызывает инструменты (`tools=`/`function_call` в коде отсутствуют); LLM только отвечает JSON на запрос.
- **Нет межролевого общения** — роли обмениваются данными только через `OrchestratorContext`, параллельных ветвей-агентов нет.
- **Нет автономных циклов** — количество повторов ограничено оркестратором (`max_attempts`, `self_critic_regenerate_max`).

Точки расширения уже заложены: `LLMGateway` — ABC с фабрикой (новый провайдер = новый класс + строка в `get_llm_gateway()`), `OrchestratorHandlers` — protocol для фаз (`app/services/phases/` — чистые функции, новую роль-агента можно добавить как новую фазу), конфиг моделей на роль — через БД. Для полноценной мультиагентности потребуется: (1) добавить tool-calling в шлюз, (2) разрешить роли инициировать действия (поиск, вызов API), (3) расширить оркестратор параллельными ветвями и общим «чёрным доской»-контекстом.

---

## 6. Итоги

1. Общение с нейросетями — структурированное: OpenAI-совместимый чат-протокол на входе, JSON-контракты на выходе, всё типизировано и санитизировано кодом.
2. Провайдерство гибкое: OpenAI «из коробки» + любой OpenAI-совместимый сервер через `base_url`; модели, ключ и промпты меняются из админки без редеплоя; поддерживаются семейство GPT-4/5 и o1.
3. Архитектура уже является мультиролевой (13 специализированных LLM-ролей под управлением детерминированного оркестратора), а stateless API позволяет использовать приложение как агента-эксперта во внешних мультиагентных системах; нативного tool-calling и автономных агентов пока нет — для них заложены точки расширения.

Связанные документы: [02_architecture.md](./02_architecture.md) (паттерны и data flow), [03_execution_flow.md](./03_execution_flow.md) (маршруты API), [08_ai_code_examples.md](./08_ai_code_examples.md) (примеры кода).
