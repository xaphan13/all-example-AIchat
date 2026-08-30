# 02 — Architecture & Patterns (Архитектура и паттерны)

## Высокоуровневая архитектура

Система построена как **модульный монолит** со слоистой архитектурой и чётким разделением ответственности:

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Frontend (React/Vite SPA)                      │
│                  Admin panel + Chat UI + API Reference                │
└──────────────────────────────┬──────────────────────────────────────┘
                               │ HTTP / SSE
┌──────────────────────────────▼──────────────────────────────────────┐
│                     Nginx (reverse proxy, optional)                   │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────────────┐
│                         FastAPI Application                           │
│  ┌─────────────┐  ┌──────────────┐  ┌───────────┐  ┌────────────┐  │
│  │ Gateway MW  │→ │ Rate Limit MW│→ │ Metrics MW│→ │  CORS MW   │  │
│  │ (WAF, IP)   │  │ (Redis)      │  │ (Prom)    │  │            │  │
│  └─────────────┘  └──────────────┘  └───────────┘  └────────────┘  │
│  ┌─────────────────────────────────────────────────────────────────┐│
│  │                      API Routes Layer                            ││
│  │  /conversations  /reply  /documents  /tickets  /admin  /auth    ││
│  └──────────────────────────────┬──────────────────────────────────┘│
└─────────────────────────────────┼───────────────────────────────────┘
                                  │
┌─────────────────────────────────▼───────────────────────────────────┐
│                       Service Layer (Business Logic)                  │
│  ┌─────────────────────────────────────────────────────────────────┐│
│  │                    AnswerService (Entry Point)                   ││
│  │  Intent Cache → Normalizer (LLM) → Orchestrator State Machine   ││
│  └──────────────────────────────┬──────────────────────────────────┘│
│  ┌──────────────────────────────▼──────────────────────────────────┐│
│  │              Orchestrator (State Machine)                        ││
│  │  UNDERSTAND → RETRIEVE → ASSESS → DECIDE → GENERATE → VERIFY    ││
│  │       ↑                    ↑                     ↓               ││
│  │   RETRY_RETRIEVE ←─────────┘              DONE/ASK_USER/ESCALATE ││
│  └──────────────────────────────┬──────────────────────────────────┘│
│  ┌──────────────┐  ┌────────────┐  ┌──────────────┐  ┌───────────┐ │
│  │ Normalizer   │  │ Retrieval  │  │ ReviewerGate │  │ Output    │ │
│  │ (LLM→QuerySpec)│ │ Service    │  │ (Claim-level)│  │ Builder   │ │
│  └──────────────┘  └────────────┘  └──────────────┘  └───────────┘ │
│  ┌──────────────┐  ┌────────────┐  ┌──────────────┐  ┌───────────┐ │
│  │ Decision     │  │ Evidence   │  │ Self-Critic  │  │ Final     │ │
│  │ Router       │  │ Quality    │  │ (LLM)        │  │ Polish    │ │
│  └──────────────┘  └────────────┘  └──────────────┘  └───────────┘ │
└─────────────────────────────────┼───────────────────────────────────┘
                                  │
┌─────────────────────────────────▼───────────────────────────────────┐
│                      Search & Storage Layer                           │
│  ┌────────────┐  ┌───────────┐  ┌─────────────┐  ┌──────────────┐  │
│  │ OpenSearch │  │  Qdrant   │  │ Embeddings  │  │  Reranker    │  │
│  │  (BM25)    │  │ (Vector)  │  │ (OpenAI)    │  │ (Local/Cohere)│  │
│  └────────────┘  └───────────┘  └─────────────┘  └──────────────┘  │
│  ┌────────────┐  ┌───────────┐  ┌─────────────┐                     │
│  │ PostgreSQL │  │  Redis    │  │  MinIO (S3) │                     │
│  │  (OLTP)    │  │ (Cache)   │  │ (Raw docs)  │                     │
│  └────────────┘  └───────────┘  └─────────────┘                     │
└─────────────────────────────────────────────────────────────────────┘
```

**Celery Worker** — отдельный процесс для async ingestion (общий образ с API).

## Основные паттерны проектирования

### 1. State Machine (Оркестратор)

`app/services/orchestrator.py` — центральный паттерн. `Orchestrator` управляет переходами состояний RAG-пайплайна через `next_action()` и `_apply_result()`. Состояния: `INIT → UNDERSTANDING → RETRIEVING → ASSESSING → DECIDING → GENERATING → REVIEWING → RETRYING → COMPLETE`. Действия: `UNDERSTAND, RETRIEVE, ASSESS_EVIDENCE, DECIDE, GENERATE, VERIFY, RETRY_RETRIEVE, DONE, ASK_USER, ESCALATE`.

### 2. Protocol-based Handlers (Strategy + Command)

`OrchestratorHandlers` — `Protocol` (structural typing). `AnswerService` реализует `execute()` и `build_output()`. Оркестратор не знает конкретных реализаций фаз — они передаются через protocol. Фазы (`app/services/phases/`) — чистые функции, вызываемые `AnswerService.execute()`.

### 3. Abstract Base Class / Factory (Search Providers)

`app/search/base.py` определяет ABC: `EmbeddingProvider`, `RerankerProvider`, `LLMGateway`. Конкретные реализации (`OpenAIGateway`, `LocalRerankerProvider`, `CohereRerankerProvider`) создаются через factory-функции (`get_llm_gateway()`, `get_reranker_provider()`, `get_embedding_provider()`), выбираемые по config.

### 4. Dependency Injection (FastAPI)

- `get_db()` — async session injection в routes
- `verify_api_key()` / `verify_admin_api_key()` — auth dependency
- `AnswerService.__init__()` принимает `retrieval`, `llm`, `reviewer`, `orchestrator` (defaults создаются лениво)
- `RetrievalService.__init__()` принимает `opensearch`, `qdrant`, `embedding_provider`, `reranker`

### 5. Dataclass Contracts (Schema Layer)

`app/services/schemas.py` — все контракты пайплайна реализованы как `@dataclass` (не Pydantic): `QuerySpec`, `RetrievalPlan`, `CandidatePool`, `EvidenceSet`, `DecisionResult`, `AnswerPlan`, `AnswerOutput`, `ReviewResult`. Это разделяет API-layer валидацию (Pydantic в `app/api/schemas.py`) от внутренних контрактов (dataclass).

### 6. Config-Driven Feature Flags

Трёхуровневая конфигурация:
1. **Environment variables** → `Settings` (`app/core/config.py`, `@lru_cache`)
2. **Database** (`app_config` table) → `archi_config.py` (13 feature flags, TTL cache 60s)
3. **Admin API** → `PUT /admin/config/*` → обновляет DB → `refresh_cache()`

### 7. Task-Aware Model Routing

`app/services/model_router.py` — routing LLM models по задаче: primary (`gpt-5.2`) для `generate`/`self_critic`, economy (`gpt-4o-mini`) для `normalizer`/`decision_router`/`evidence_quality`/etc.

### 8. LLM-as-Orchestrator (Anti-Hardcoding)

Согласно `.cursor/rules/project-development.mdc`: intent, required_evidence, quality, retry strategy — определяются LLM, а не keyword rules. Код содержит только санитизацию/коерцию LLM-вывода, не бизнес-логику.

## Схема потока данных (Data Flow)

### RAG Query Flow (основной)

```
User Message
    │
    ▼
[POST /v1/conversations/{id}/messages]
    │
    ├─ Guardrails: check_injection() → sanitize_user_input()
    │
    ├─ Save user message to DB (Message table)
    │
    ├─ Load conversation history (truncate_for_pipeline)
    │
    ▼
AnswerService.generate(query, history, trace_id)
    │
    ├─ Intent Cache: match_intent(query) → predefined answer? → return
    │
    ├─ Language Detection: detect_language(query)
    │
    ├─ Normalizer (LLM): normalize(query, history) → QuerySpec
    │   ├─ LLM call (gpt-4o-mini, JSON schema)
    │   ├─ Sanitize: intent, risk, evidence, answer_type, slots
    │   ├─ Derive: evidence_families, hypotheses, retrieval_profile
    │   └─ skip_retrieval? → canned_response → return
    │
    ├─ Create OrchestratorContext(query, query_spec, history)
    │
    ▼
Orchestrator.run(ctx, handlers=AnswerService)
    │
    ├─ UNDERSTAND: (already done — query_spec ready)
    │
    ├─ RETRIEVE: execute_retrieve()
    │   ├─ Build RetrievalPlan (from QuerySpec + retry_strategy)
    │   ├─ Parallel: BM25 (OpenSearch) + Embedding (OpenAI) + Vector (Qdrant)
    │   │   ├─ Primary + supporting + diversity fan-out (asyncio.gather)
    │   │   └─ Score calibration (page_kind, product_family weights)
    │   ├─ Merge: RRF (Reciprocal Rank Fusion) or simple dedupe
    │   ├─ Rerank: Local/Cohere/Custom reranker
    │   ├─ Evidence Selector (LLM): coverage-aware selection
    │   ├─ Evidence Set Builder: EvidenceSet from CandidatePool
    │   ├─ Evidence Hygiene: boilerplate, URL coverage (parallel, asyncio.to_thread)
    │   └─ Evidence Evaluator (LLM, optional): relevance → retry advice
    │
    ├─ ASSESS_EVIDENCE: execute_assess_evidence()
    │   ├─ Evidence Quality Gate (LLM v2): is_sufficient? completeness, actionability
    │   ├─ Fail + can_retry? → RETRY_RETRIEVE
    │   └─ Pass → DECIDE
    │
    ├─ DECIDE: execute_decide()
    │   ├─ Decision Router: deterministic lane assignment
    │   │   ├─ CANDIDATE_VERIFY / PASS_EXACT / PASS_PARTIAL → GENERATE
    │   │   ├─ TARGETED_RETRY → RETRY_RETRIEVE (if can_retry)
    │   │   ├─ ASK_USER → ASK_USER (terminal)
    │   │   └─ ESCALATE → ESCALATE (terminal)
    │   └─ Build AnswerPlan (lane, allowed_claim_scope, must_include/avoid)
    │
    ├─ GENERATE: execute_generate()
    │   ├─ Relevance Check: is conversation history relevant? (LLM)
    │   ├─ Prior Citations Injection: inject URLs from prior assistant messages
    │   ├─ Reasoning Prepass (LLM, optional): evidence summary, options, coverage
    │   ├─ LLM Generation (gpt-5.2): system_prompt + evidence + answer_plan + history
    │   ├─ Parse LLM response: answer, citations, confidence, decision
    │   ├─ Self-Critic (LLM, optional): critique → regenerate on fail
    │   └─ Build AnswerCandidate (answer_mode, support_level, disclaimers)
    │
    ├─ VERIFY: execute_verify()
    │   ├─ ReviewerGate.review()
    │   │   ├─ AnswerCalibrator: exact-answer type check, overclaim detection
    │   │   ├─ Claim-level review: segment_claims → is_risky/policy/number
    │   │   ├─ Trim unsupported claims (if claim_level_review_enabled)
    │   │   ├─ Downgrade lane (PASS_EXACT → PASS_PARTIAL)
    │   │   ├─ Calibrate confidence (cap by mode + support_level)
    │   │   └─ Status: PASS / TRIM_UNSUPPORTED / DOWNGRADE_LANE / ASK_USER / ESCALATE
    │   ├─ Hypothesis Judge: select best hypothesis from history
    │   └─ Targeted Retry: schedule retry with suggested_queries (if retryable)
    │
    ├─ RETRY_RETRIEVE (if applicable):
    │   ├─ plan_retry(missing_signals, evidence_eval) → RetryStrategy
    │   └─ → RETRIEVE (attempt++)
    │
    ▼
Terminal Action (DONE / ASK_USER / ESCALATE)
    │
    ├─ build_output()
    │   ├─ DONE: render_calibrated_candidate() → final_polish() → AnswerOutput
    │   ├─ ASK_USER: decision_router answer or default → AnswerOutput
    │   └─ ESCALATE: error/handoff message → AnswerOutput
    │   └─ build_flow_debug(): trace_id, evidence, LLM usage, stage_reasons, rollout_flags
    │
    ├─ Save assistant message to DB (Message with debug_metadata)
    ├─ Save citations to DB (Citation table)
    └─ Return SendMessageResponse
```

### Ingestion Flow

```
POST /admin/ingest (documents list)
    │
    ├─ Celery: ingest_documents_task (async queue)
    │
    ▼
IngestionService.ingest_document(doc, session)
    │
    ├─ prepare_document(): _clean_html() → _chunk_by_semantic_boundaries() → _expand_to_semantic_units()
    ├─ Checksum (idempotency): skip if unchanged
    ├─ Enrich metadata: _with_taxonomy_metadata (page_kind, product_family)
    ├─ Store raw content in MinIO (optional)
    ├─ Create/update Document in PostgreSQL
    ├─ Delete old chunks from OpenSearch + Qdrant (if re-index)
    │
    ├─ For each PreparedChunk:
    │   ├─ Create Chunk in PostgreSQL
    │   ├─ Embed: embedder.embed([chunk_text]) → vector
    │   ├─ Qdrant: upsert_chunk(id, vector, metadata)
    │   └─ OpenSearch: index_chunk(id, body, doc_type, metadata)
    │
    └─ Commit transaction
```

## Управление состоянием, кэширование и конфигурация

### Состояние

- **Pipeline state**: `OrchestratorContext` (dataclass) — единый source of truth для одного запроса. Передаётся через фазы, не сохраняется между запросами.
- **Conversation state**: PostgreSQL (`Conversation` → `Message` → `Citation`). History загружается из DB при каждом запросе, truncat'ится до `conversation_history_max_messages`.
- **Config cache**: In-memory `_cache` dict в `archi_config.py`, `branding_config.py`, `llm_config.py`, `doc_type_service.py`. Refresh на startup и при admin update.

### Кэширование

| Кэш | Технология | TTL | Ключ | Инвалидация |
|---|---|---|---|---|
| LLM responses | Redis (`llm_cache:{sha256}`) | `llm_cache_ttl_seconds` (3600s) | messages + model + temperature hash | `clear_llm_cache()` (admin) |
| Query rewrites | Redis (`qr_cache:{sha256}`) | `query_rewriter_cache_ttl_seconds` (3600s) | query + history hash | `clear_query_rewriter_cache()` (admin) |
| Rate limit | Redis (`rl:{ip/user}`) | Sliding window (60s) | IP or X-External-User-Id | Auto-expire |
| Config flags | In-memory dict | 60s TTL (manual refresh) | Feature flag name | `refresh_cache()` on admin update |
| Settings | `@lru_cache` | Process lifetime | — | Process restart |

### Конфигурация

- **Primary**: `.env` file → `Settings` (Pydantic `BaseSettings`, `@lru_cache`)
- **Runtime overrides**: DB `app_config` table → admin API (`PUT /admin/config/*`)
- **Feature flags** (13): `language_detect_enabled`, `evidence_evaluator_enabled`, `evidence_quality_use_llm`, `evidence_quality_llm_v2`, `self_critic_enabled`, `final_polish_enabled`, `doc_type_classifier_enabled`, `page_kind_filter_enabled`, `llm_task_aware_routing_enabled`, etc.
- **Prompt layering**: Core + Domain (`support`/`legal`/`generic`) + Custom rules — все из DB
