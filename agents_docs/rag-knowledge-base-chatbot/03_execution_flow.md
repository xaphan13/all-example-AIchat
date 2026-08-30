# 03 — Execution Flow (Логика и работа кода)

## Жизненный цикл приложения

### Инициализация (Startup)

1. **Container/Docker**: `docker-entrypoint.sh` запускает миграции Alembic, при необходимости Playwright install, затем `uvicorn app.main:app`.
2. **`app/main.py` → `create_app()`**:
   - `get_settings()` — загрузка env-конфигурации (lru_cache singleton).
   - `FastAPI` instance (docs скрываются при `DOCS_ENABLED=false`, `openapi.json` всегда доступен).
   - Middleware chain (порядок регистрации = порядок выполнения):
     1. `CORSMiddleware` (origins из `CORS_ORIGINS`)
     2. `GatewayMiddleware` (WAF, IP rules, body size) — BaseHTTPMiddleware
     3. `MetricsMiddleware` (HTTP metrics)
     4. `rate_limit_middleware` (Redis token bucket)
   - Router'ы монтируются с `api_prefix` (`/v1`).
   - `setup_tracing(app)` — OpenTelemetry instrumentation + `X-Trace-Id` middleware.

### Lifespan (async startup)

```python
@app.lifespan
async def lifespan(app):
    setup_logging(json_logs=True, log_level="INFO")
    # Загрузка конфигурации из DB в in-memory cache
    await refresh_cache(session)          # branding (prompts, intents)
    await refresh_doc_type_cache(session) # doc_types catalog
    await refresh_llm_config(session)     # LLM model/keys
    await refresh_archi_config(session)   # feature flags (13 toggles)
    yield
    # Shutdown
```

Кэш конфигурации обновляется на startup и при каждом admin update (invalidation через `refresh_cache()` в route handlers).

### Завершение (Shutdown)

- Логируется `application_shutdown`.
- Connections (DB engine, Redis) закрываются через контекстные менеджеры при выходе процесса.
- Активные Celery-таски продолжают работать в worker-процессе.

## Ключевые бизнес-процессы

### Процесс 1: Ответ на сообщение (core RAG)

Описание потока в `docs/02_architecture.md` (Data Flow). Здесь — детали реализации:

**`AnswerService.generate()`** (`app/services/answer_service.py`):
1. Сброс контекстных переменных: `llm_usage_var.set([])`, при `debug_llm_calls` → `llm_call_log_var.set([])`.
2. **Intent Cache** (`match_intent(query)`, regex по таблице `intents`): при совпадении возвращает готовый ответ без LLM/retrieval.
3. **Language Detection** (`detect_language`) — non-LLM detector.
4. **Normalizer** (LLM): `normalize(query, history, source_lang)` → `QuerySpec`. При падении LLM → `_build_minimal_fallback()` (generic profile, pipeline жив).
5. **skip_retrieval**: canned response для приветствий/out-of-scope — без LLM и retrieval.
6. Создание `OrchestratorContext` с `max_attempts = max(max_retrieval_attempts, 1 + fallback_hypothesis_count)`.
7. `orchestrator.run(ctx, self)` — цикл до терминального действия (максимум 50 итераций).

**Orchestrator loop** (`app/services/orchestrator.py`):
- `next_action(ctx, reviewer_status, has_evidence)` — чистая функция переходов.
- `handlers.execute(ctx, action)` — диспетчеризация на фазы.
- Исключения в фазе → `build_output(ctx, ESCALATE)` (graceful degradation).
- `max_iterations=50` — защита от бесконечного цикла.

### Процесс 2: Retry lifecycle

```
ASSESS fail (quality gate) или DECIDE → TARGETED_RETRY
    │
    ▼
plan_retry(missing_signals, evidence_eval_result, query_spec) → RetryStrategy
    │  (boost_patterns, filter_doc_types, suggested_query, context_expansion)
    │
    ▼
build_retrieval_plan_for_attempt(...) → RetrievalPlan (attempt=2)
    │  (fallback hypotheses: fallback_capability, fallback_policy)
    │
    ▼
RETRIEVE (attempt++) → ASSESS → ...
```

- **Evidence Evaluator** (LLM, опционально): оценивает релевантность evidence, выдаёт `retry_needed` + `retry_boost_terms` + `retry_doc_types` + `suggested_query`.
- **Quality gate fail** → retry через `plan_retry()`.
- **Verify fail** (type_mismatch/overclaim/unsupported_exact) → `_schedule_verify_targeted_retry()`: один целевой retry с `reviewer_result.suggested_queries[0]`.
- `max_retrieval_attempts=3` (по умолчанию), после исчерпания → `ASK_USER` / `ESCALATE`.

### Процесс 3: Ingestion документа

```
Admin API → POST /admin/ingest → Celery task (ingest_documents_task)
    │
    ▼
_ingest_one(doc) → async_session_factory → IngestionService.ingest_document()
    │
    ├─ prepare_document(): HTML cleaning (_clean_html) → heading-aware chunking
    │   (_chunk_by_semantic_boundaries) → semantic units (_expand_to_semantic_units)
    ├─ Idempotency: sha256 checksum — unchanged → skip re-embed, update metadata only
    ├─ Raw content → MinIO (best-effort)
    ├─ Document row upsert (PostgreSQL), старые chunks удаляются из БД + индексов
    ├─ Для каждого chunk: создание Chunk row → embedding → Qdrant upsert → OpenSearch index
    └─ Commit
```

### Процесс 4: WHMCS тикеты

```
crawl_whmcs_tickets.py / POST /admin/tickets/crawl
    │
    ├─ Playwright browser: login → список тикетов → detail (subject, description, replies)
    │
    ▼
Ticket row в PostgreSQL (external_id уникальный)
    │
    ├─ Approval workflow: status = pending → (approve/reject) через admin API
    │
    ├─ Approve → ticket_sync: конвертация в источник для ingestion (conversation doc_type)
    │
    └─ Conversation создаётся с source_type=ticket, source_id=whmcs_ticket_id
```

### Процесс 5: Suggest Reply (внешние платформы)

`POST /v1/reply/generate` (`app/api/routes/reply.py`):
- Stateless: `AnswerService.generate()` без персистентности.
- Принимает `query` + опциональный `conversation_history` (truncated до 20 сообщений).
- Возвращает `answer`, `decision`, `citations`, `confidence`, `followup_questions`, `debug`.
- Используется для WHMCS/Zendesk/livechat: агент видит сгенерированный ответ в UI.

## Роутинг и middleware

### Middleware chain (порядок выполнения)

| № | Middleware | Файл | Назначение |
|---|---|---|---|
| 1 | `CORSMiddleware` | fastapi | CORS headers |
| 2 | `GatewayMiddleware` | `app/core/gateway.py` | WAF regex (injection/jailbreak), IP blocklist/allowlist, body size limit (1MB), re-inject body |
| 3 | `MetricsMiddleware` | `app/core/metrics_middleware.py` | Prometheus HTTP metrics |
| 4 | `rate_limit_middleware` | `app/core/rate_limit.py` | Redis sliding window (60 req/min), admin Bearer bypass |
| 5 | `add_trace_id_middleware` | `app/core/tracing.py` | X-Trace-Id generation/propagation (добавляется внутри setup_tracing) |

### Routes

| Route | Auth | Назначение |
|---|---|---|
| `GET /v1/health` | none | Liveness probe |
| `POST /v1/auth/login` | none | JWT login (username/password) |
| `POST /v1/auth/tokens` | JWT | Create API token (sk_*) |
| `GET/POST /v1/conversations` | API key | List/create conversations |
| `GET/PATCH/DELETE /v1/conversations/{id}` | API key | Conversation CRUD |
| `POST /v1/conversations/{id}/messages` | API key | Sync answer generation |
| `POST /v1/conversations/{id}/messages:stream` | API key | SSE streaming answer |
| `POST /v1/reply/generate` | API key | Stateless suggested reply |
| `GET/POST /v1/documents` | API key | Document CRUD |
| `POST /v1/documents/fetch-from-url` | API key | Fetch URL content |
| `POST /v1/documents/crawl-website` | API key | Crawl website → ingest |
| `GET/POST /v1/tickets` | API key | Ticket list (filters, pagination) |
| `GET /v1/tickets/{id}` | API key | Ticket detail + messages |
| `POST /v1/tickets/{id}/approval` | Admin | Approve/reject ticket |
| `GET /v1/dashboard/*` | Admin | Metrics/statistics |
| `POST /v1/admin/ingest` | Admin | Trigger Celery ingestion |
| `POST /v1/admin/ingest-from-source` | Admin | Ingest from source JSON files |
| `GET/PUT /v1/admin/config/*` | Admin | App config, LLM config, prompts, archi flags |
| `POST /v1/admin/intents` | Admin | Intent cache CRUD |
| `POST /v1/admin/doc-types` | Admin | DocType catalog CRUD |
| `POST /v1/admin/tickets/crawl` | Admin | WHMCS crawl |
| `POST /v1/admin/branding/generate` | Admin | LLM auto-generate branding |

### Auth flow

1. **Login**: `POST /auth/login` → bcrypt verify → JWT (HS256, `jwt_expire_minutes`) → `Authorization: Bearer`.
2. **API key**: `X-API-Key` header → env `API_KEY` сравнение (или dev-mode, если пустой) → DB token `sk_*` (hash lookup).
3. **Admin**: `X-Admin-API-Key` / JWT с `role=admin` / `sk_*` от admin user.
4. Rate limit bypass только для admin Bearer JWT.

## Механизмы обработки ошибок и логирования

### Обработка ошибок

| Слой | Стратегия |
|---|---|
| **API** | FastAPI `HTTPException` (404, 400, 401, 413, 429, 502); HTTP code mapping |
| **Orchestrator** | try/except вокруг `handlers.execute()` → `build_output(ctx, ESCALATE)` + `ctx.extra["error"]` |
| **Retrieval** | Fallback-цепочка: `_search_opensearch_safe` (TypeError → fallback kwargs → empty), `_search_qdrant_safe` (thread + timeout), reranker failure → original scores |
| **Normalizer** | LLM fail → `_build_minimal_fallback()` (пайплайн не падает) |
| **Ingestion** | Celery task per-doc try/except → `status: error` в результатах, idempotency по checksum |
| **External services** | `asyncio.wait_for` timeout'ы (6s OpenSearch, 6s Qdrant, 8s embedding, 60s LLM), semaphores (24 concurrency) |

### Graceful degradation (ступенчатая деградация)

1. LLM unavailable → normalizer fallback → generic profile → retrieval без LLM → top-k evidence → generation без plan.
2. Reranker unavailable → original BM25+RRF scores.
3. Redis unavailable → rate limit skipped, LLM cache skipped, query rewriter cache skipped.
4. Vector search fails → BM25 only.
5. Evidence evaluator / hygiene fail → логируется, не блокирует.

### Логирование

- **`app/core/logging.py`**: structured logging через structlog (json logs), `trace_id_var` ContextVar, PII redaction (`redact_emails`, `redact_phones`), event-ключи (kebab-case, e.g. `application_startup`, `orchestrator_terminated`).
- **`app/services/flow_debug.py`**: `_pipeline_log()` — пишет каждый этап пайплайна (answer_service, normalizer, retrieve, assess, decide, generate, verify, api) в лог и в Redis `flow_debug:{trace_id}` (для веба). Контролируется `PIPELINE_LOGGING_ENABLED`.
- **Debug payload**: `build_flow_debug()` — собирает в `AnswerOutput.debug` полный трейс: evidence pack, LLM messages, tokens/cost, quality report, retry strategy, decision router, review result, stage_reasons, rollout flags. Сохраняется в `Message.debug_metadata` (JSONB).
- **Audit**: `AuditLLMCall` таблица — каждый LLM call (model, provider, tokens, latency, prompt_hash).
- **Metrics**: Prometheus (LLM cost, tokens, latency; retrieval hit/miss; decisions; escalations; self-critic regenerations).
- **Tracing**: OpenTelemetry `X-Trace-Id` propagation через response headers.

### Rate limiting

- Redis sorted-set sliding window (`rl:{ip}` или `rl:user:{X-External-User-Id}`).
- Default: 60 req/60s, конфигурируется (`rate_limit_requests`, `rate_limit_window_seconds`).
- Redis unavailable → лимит пропускается (fail-open).
- Admin Bearer requests — bypass.
