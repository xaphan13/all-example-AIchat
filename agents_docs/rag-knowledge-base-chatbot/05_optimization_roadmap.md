# 05 — Optimization Roadmap (Предложения по развитию)

## Архитектурные улучшения

### A1. Декомпозиция `retrieval.py` → модульная архитектура

**Текущее состояние**: `app/services/retrieval.py` — 1250+ строк, один класс `RetrievalService` с планированием, калибровкой, fusion, bundle-логикой, stats-сборкой.

**Предложение**:
- `app/services/retrieval/runner.py` — оркестрация parallel fetch + merge + rerank (высокий уровень).
- `app/services/retrieval/calibration.py` — `_apply_search_calibration`, `_apply_rerank_calibration`, `_score_calibration_factor`.
- `app/services/retrieval/merge.py` — `_merge_with_rrf`, `_merge_simple`, `_dedupe_chunks`.
- `app/services/retrieval/bundles.py` — `_fetch_bm25_bundle`, `_fetch_vector_bundle`, `_Bm25Bundle`, `_VectorBundle`.
- `app/services/retrieval/evidence_pipeline.py` — evidence selector + set builder + ensure_doc_type_min логика.

**Обоснование**: тестируемость, читаемость, возможность профилировать каждый этап.

### A2. Единый пул Redis-соединений

**Текущее состояние**: каждый вызов `_get_cached()` / `_set_cached()` / `rate_limit_middleware` создаёт новое `redis.from_url()` соединение и закрывает его вручную.

**Предложение**: ввести `app/core/redis.py` с `get_redis_pool()` ( singleton `redis.asyncio.ConnectionPool`), использовать во всех потребителях (LLM cache, query rewriter cache, rate limit, flow debug). Connection pool автоматически переиспользует соединения, даёт backpressure.

**Обоснование**: снижение latency на установку соединения (TLS handshake), надёжность при пиковых нагрузках, единая точка конфигурации retry/timeout.

### A3. Celery worker с persistent event loop

**Текущее состояние**: `worker/tasks.py` использует `asyncio.run(_ingest_one(doc))` в цикле — новый event loop на каждый документ.

**Предложение**: использовать `celery.app.task` с `acks_late=True` и `prefork` worker + `asyncio.get_event_loop().run_until_complete()` в общем loop, либо перейти на `arq` / `dramatiq` с native async, либо использовать `uvicorn` worker + asyncio task queue (например, `aiojobs`).

Альтернатива: вынести ingestion в отдельный FastAPI microservice с `BackgroundTasks` + in-memory queue, если объёмы невелики.

**Обоснование**: `asyncio.run()` создаёт/уничтожает event loop — overhead при bulk ingestion (100+ документов). Вложенные `embed()` вызовы не переиспользуют client connection pools.

### A4. Типизация `ctx.extra` → явные поля `OrchestratorContext`

**Текущее состояние**: `OrchestratorContext.extra: dict[str, Any]` — де-факто «чёрный ящик» для передачи `answer_candidate`, `llm_resp`, `messages`, `hypothesis_history`, `verify_targeted_retry_*`, `error`, `conversation_relevance`.

**Предложение**: выделить типизированные поля:
```python
@dataclass
class OrchestratorContext:
    # ... существующие поля ...
    llm_response: LLMResponse | None = None
    messages: list[dict[str, str]] = field(default_factory=list)
    answer_candidate: AnswerCandidate | None = None
    hypothesis_history: list[dict] = field(default_factory=list)
    conversation_relevance: RelevanceCheckResult | None = None
    retry_strategy_applied: dict | None = None
    error: str | None = None
    verify_targeted_retry: VerifyRetryState | None = None
    extra: dict[str, Any] = field(default_factory=dict)  # только для ad-hoc debug
```

**Обоснование**: типобезопасность, автодополнение в IDE, явные контракты между фазами, невозможность рассинхронизации ключей.

### A5. Единый config-cache базовый класс

**Текущее состояние**: `archi_config.py`, `branding_config.py`, `llm_config.py`, `doc_type_service.py` — четыре модуля с одинаковым паттерном (DB load → in-memory `_cache` dict → TTL refresh).

**Предложение**: ввести `app/core/config_cache.py`:
```python
class ConfigCache[T]:
    async def refresh(self, session: AsyncSession) -> None: ...
    def get(self, key: str, default: T) -> T: ...
```
Подклассы определяют `keys`, `parse_value`, `query`. Убирает ~300 строк дублирования.

### A6. Удаление deprecated флагов и legacy путей

**Текущее состояние**: `Settings` содержит ~10 deprecated полей (`fallback_llm_decides_enabled`, `chunk_filter_enabled`, `decision_router_use_llm`, `normalizer_use_llm` и др.), помеченных `[Deprecated]` или `[Removed]`. Код всё ещё проверяет их в условных ветках.

**Предложение**: провести мажорную чистку (с bump версии и миграцией env): удалить из `Settings`, убрать условные ветки, обновить `.env.example`, добавить migration для очистки `app_config` записей. Снизит когнитивную нагрузку и риск случайного включения.

## Оптимизация производительности

### P1. Batch embedding при ingestion

**Текущее состояние**: `IngestionService.ingest_document()` эмбеддит чанки по одному (`embed([chunk_text])`) в цикле. Для документа с 50 чанками — 50 отдельных API вызовов.

**Предложение**: батчить эмбеддинги (до 100 текстов за запрос — OpenAI поддерживает). Ввести `embed_batch(texts: list[str], batch_size: int = 64)` в `EmbeddingProvider`.

**Эффект**: 5-10x ускорение ingestion для больших документов, снижение cost.

### P2. Streaming generation для SSE

**Текущее состояние**: `send_message_stream` генерирует полный ответ через `AnswerService.generate()`, затем разбивает на 100-char chunks для SSE. Реального стриминга нет — клиент ждёт полного ответа.

**Предложение**: добавить `AnswerService.generate_stream()` с real-time проксированием LLM stream chunks. Требует:
- `LLMGateway.chat_stream()` (OpenAI `stream=True`).
- Оркестратор должен отдавать partial answer после GENERATE (до VERIFY), либо стримить pre-verify ответ с последующей коррекцией.
- Verify/trim применять post-stream (отправить `type: "correction"` event если trim/downgrade произошёл).

**Эффект**: perceived latency снижается с ~5-15s до <1s (time to first token).

### P3. Кэширование QuerySpec по (query + history_hash)

**Текущее состояние**: `normalizer.normalize()` делает LLM-вызов на каждый запрос, даже если идентичный запрос уже обрабатывался.

**Предложение**: кэшировать `QuerySpec` в Redis по `sha256(query + truncated_history)`, TTL 1h. Инвалидация при изменении system prompt / config.

**Эффект**: ~30-50% запросов (повторные, переформулировки) — без LLM normalizer call.

### P4. OpenSearch bulk indexing для ingestion

**Текущее состояние**: `ingest_document()` индексирует чанки по одному (`index_chunk` per chunk).

**Предложение**: использовать `bulk()` из `opensearchpy.helpers` (уже импортирован в `opensearch_client.py`). Накапливать actions, flush пачкой.

**Эффект**: 3-5x ускорение ingestion, снижение round-trips.

### P5. Pre-compute evidence hygiene signals при ingestion

**Текущее состояние**: `compute_hygiene(evidence)` выполняется на каждом retrieval — regex-паттерны по всем чанкам.

**Предложение**: при ingestion вычислять hygiene-сигналы (boilerplate_ratio, content_density, has_url, has_number_unit) и сохранять в `chunk_metadata`. В retrieval — читать из metadata.

**Эффект**: устранение regex-прохода в hot path, ~10-30ms экономии на запрос.

### P6. Параллельный evidence_quality + decision_router

**Текущее состояние**: ASSESS → DECIDE выполняются последовательно.

**Предложение**: если quality gate pass, decision router можно запустить параллельно с evidence quality (они независимы по входу — quality смотрит на evidence, router на QuerySpec + quality_report). `asyncio.gather(assess, decide)` с merge результатов.

**Эффект**: ~100-300ms экономии (один LLM call параллельно с другим).

### P7. Qdrant query_points API

**Текущее состояние**: `QdrantSearchClient.search()` использует `search()` (legacy) или scroll-based подход.

**Предложение**: перейти на `query_points()` API (Qdrant v1.10+, уже требуется в `docker-compose.yml`), который поддерживает fused filtering + scoring в одном запросе.

**Эффект**: ниже latency, лучше фильтрация, нативная поддержка payload filters.

## Рефакторинг (первоочередные файлы)

| Приоритет | Файл | Объём | Обоснование |
|---|---|---|---|
| 🔴 1 | `app/services/retrieval.py` | 1250+ строк | Декомпозиция (A1), вынос calibration/merge/bundles |
| 🔴 2 | `app/services/normalizer.py` | 1370+ строк | Вынос sanitize-хелперов в `normalizer_utils.py`, удаление rule-based веток (соответствие `.cursor/rules`) |
| 🔴 3 | `app/services/output_builder.py` | 353 строки | Дедупликация 3 веток через `_build_debug_payload(ctx, **overrides)` |
| 🔴 4 | `app/services/llm_gateway.py` | 230 строк | Redis pool (A2), вынос cache в отдельный класс |
| 🟠 5 | `app/services/reviewer.py` | 830 строк | Вынос `AnswerCalibrator` в отдельный модуль, упрощение `_try_trim_or_downgrade` |
| 🟠 6 | `app/api/routes/admin.py` | 914 строк | Разделение на `admin/ingest.py`, `admin/config.py`, `admin/tickets.py`, `admin/branding.py` |
| 🟠 7 | `app/search/opensearch_client.py` | 585 строк | Вынос index config, query builder, bulk indexer в подмодули |
| 🟡 8 | `app/services/orchestrator.py` | 466 строк | Типизация `ctx.extra` (A4), вынос `_schedule_verify_targeted_retry` в `retry_state.py` |
| 🟡 9 | `app/services/retry_planner.py` + `retrieval_planner.py` | — | Объединение или чёткое разделение ответственности |
| 🟡 10 | `app/core/config.py` | 592 строки | Удаление deprecated полей (A6), группировка по namespace |

## Рекомендации по улучшению DX (Developer Experience)

### D1. Тесты

**Текущее состояние**: 27+ тестов, покрывающих ключевые компоненты (orchestrator, retrieval, normalizer, reviewer, evidence quality/selector, decision router, self-critic, LLM gateway, query rewriter, claim parser). `pytest-asyncio` с `asyncio_mode = "auto"`.

**Рекомендации**:
- Добавить integration-тесты для `AnswerService.generate()` end-to-end с mock LLM/retrieval (частично есть в `test_rag_integration.py` — расширить).
- Добавить contract-тесты для LLM JSON schema (normalizer, evidence_quality, evidence_selector) — тест на устойчивость к malformed LLM output.
- Добавить load-тесты (locust/k6) для rate limit + retrieval concurrency.
- Добавить тесты для SSE streaming endpoint.
- Целевой coverage: ≥80% для `services/`, ≥90% для `core/`.

### D2. CI/CD

**Текущее состояние**: нет явного CI-конфига в репозитории (нет `.github/workflows/`, `gitlab-ci.yml` и т.п.).

**Рекомендации**:
- GitHub Actions / GitLab CI pipeline:
  1. `lint` (ruff/flake8 + mypy --strict для `app/`)
  2. `test` (pytest с coverage report)
  3. `build` (Docker image build + push)
  4. `migrate-check` (alembic upgrade --sql --from=head --to=head)
- Pre-commit hooks: ruff, mypy, end-of-file-fixer.
- Автоматический alembic migration generation при merge в main (через `alembic revision --autogenerate`).

### D3. Локальный запуск

**Текущее состояние**: `docker-compose.dev.yml` + `Makefile` (команды `make dev`, `make test`, `make create-admin`).

**Рекомендации**:
- Добавить `make lint`, `make typecheck`, `make migrate`, `make seed` (demo data).
- Добавить `make debug-query QUERY="..."` — CLI для запуска RAG pipeline с выводом flow_debug.
- Документировать hot-reload для frontend + backend в `README.md`.
- Добавить `.env.local` template с pre-filled dev values.

### D4. Наблюдаемость (Observability)

**Текущее состояние**: Prometheus metrics, OpenTelemetry tracing, structured logging, `_pipeline_log` для flow debug.

**Рекомендации**:
- Добавить Grafana dashboard JSON (LLM cost, tokens, latency p50/p95/p99; retrieval hit rate; decision distribution; escalation rate).
- Настроить OpenTelemetry exporter на Jaeger/Tempo (сейчас только ConsoleSpanExporter при debug).
- Добавить health check для зависимостей: `GET /v1/health` должен проверять PostgreSQL, Redis, OpenSearch, Qdrant connectivity.
- Добавить `GET /v1/health/ready` (readiness probe) для k8s.

### D5. Документация API

**Текущее состояние**: FastAPI auto-docs (`/docs`, `/redoc`), `ApiReference.tsx` в frontend.

**Рекомендации**:
- Добавить OpenAPI examples для каждого endpoint.
- Документировать `debug` payload структуру (сейчас opaque dict).
- Добавить changelog для API versioning (breaking changes).

### D6. Безопасность (Security hardening)

- Внедрить SSRF protection для `fetch-from-url` / `crawl-website`: блокировать private IP ranges (RFC 1918, 169.254.x.x, localhost).
- Добавить constant-time comparison для API key validation (`hmac.compare_digest`).
- Настроить OpenSearch security (TLS, basic auth) для production.
- Добавить `Content-Security-Policy` headers в nginx config.
- Регулярный audit зависимостей (`pip-audit` / `safety` в CI).

## Приоритизированный roadmap (кратко)

| Спринт | Задачи | Эффект |
|---|---|---|
| **Sprint 1** (1-2 нед) | A2 (Redis pool), P1 (batch embedding), P4 (bulk indexing), D4 (Grafana dashboard) | -30% ingestion time, стабильность под нагрузкой |
| **Sprint 2** (2-3 нед) | A1 (retrieval decomposition), A4 (ctx.extra typing), P3 (QuerySpec cache) | -20% query latency, читаемость |
| **Sprint 3** (2-3 нед) | A6 (legacy cleanup), A5 (config cache base), P2 (real streaming SSE) | UX улучшение, снижение сложности |
| **Sprint 4** (1-2 нед) | D2 (CI/CD), D3 (DX), D6 (security hardening) | Production readiness |
| **Sprint 5** (2 нед) | P5 (pre-compute hygiene), P6 (parallel assess+decide), P7 (Qdrant query_points) | Performance fine-tuning |
