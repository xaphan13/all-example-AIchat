# 01 — Project Structure (Карта проекта)

## Назначение проекта

**Support AI Assistant** — enterprise-grade RAG (Retrieval-Augmented Generation) чат-бот для поддержки клиентов. Система извлекает информацию из базы знаний (документы, политики, FAQ, прайс-листы, тикеты WHMCS) и генерирует обоснованные ответы с цитатами. Архитектура построена на гибридном поиске (BM25 + vector + rerank) и многофазном LLM-пайплайне с оркестратором состояния.

Проект поддерживает: API для чата (sync/stream), генерацию suggested-reply для внешних helpdesk-платформ, ingestion документов (URL/crawl/file), WHMCS-краулер тикетов, админ-панель (React), multi-tenant branding, JWT/API-key аутентификацию.

## Дерево директорий и ключевых файлов

```
rag-knowledge-base-chatbot/
├── app/                          # Основной backend (FastAPI)
│   ├── main.py                   # Точка входа FastAPI: create_app(), lifespan, middleware chain
│   ├── __init__.py
│   │
│   ├── api/                      # API слой (роуты, схемы запросов/ответов)
│   │   ├── schemas.py            # Pydantic-схемы API: ConversationResponse, IngestRequest, ArchiConfigResponse, etc.
│   │   ├── routes/
│   │   │   ├── conversations.py  # CRUD бесед + send_message (sync/SSE stream) → AnswerService
│   │   │   ├── reply.py          # POST /v1/reply/generate — stateless suggested-reply для внешних платформ
│   │   │   ├── documents.py      # CRUD документов, fetch-from-url, crawl-website, re-crawl
│   │   │   ├── tickets.py        # Список тикетов, detail, approval workflow (pending→approved→rejected)
│   │   │   ├── admin.py          # Admin: ingest, config (prompts, LLM, branding, intents, doc-types), crawl WHMCS
│   │   │   ├── auth.py           # Login (JWT), create API token, current user
│   │   │   ├── dashboard.py      # Метрики для админ-панели (counts, retrieval stats, eval results)
│   │   │   └── health.py         # Health check endpoint
│   │   └── __init__.py
│   │
│   ├── core/                     # Инфраструктурный слой (cross-cutting concerns)
│   │   ├── config.py             # Settings (Pydantic BaseSettings) — все env-параметры, lru_cache singleton
│   │   ├── auth.py               # Аутентификация: Bearer JWT, X-API-Key (env + DB token sk_*), admin verify
│   │   ├── gateway.py            # GatewayMiddleware: request size limit, IP blocklist/allowlist, WAF patterns
│   │   ├── guardrails.py         # Input sanitization, injection/jailbreak detection (regex patterns)
│   │   ├── rate_limit.py         # Redis-based token bucket rate limiting (per IP / X-External-User-Id)
│   │   ├── logging.py            # Structured logging (structlog), PII redaction, trace_id ContextVar
│   │   ├── tracing.py            # OpenTelemetry tracing, Prometheus metrics ASGI, X-Trace-Id middleware
│   │   ├── metrics.py            # Prometheus counters/histograms: LLM tokens, cost, retrieval, decisions
│   │   ├── metrics_middleware.py # HTTP request metrics middleware (latency, status codes)
│   │   ├── storage.py            # Object storage abstraction (MinIO/S3) для raw document storage
│   │   └── __init__.py
│   │
│   ├── db/                       # Слой базы данных
│   │   ├── models.py             # SQLAlchemy ORM модели: Document, Chunk, Conversation, Message, Citation,
│   │   │                         #   AppConfig, Intent, DocTypeModel, User, ApiToken, Ticket, AuditLLMCall, EvalCase/Result
│   │   ├── session.py            # Async engine, async_session_factory, get_db() FastAPI dependency
│   │   └── __init__.py
│   │
│   ├── search/                   # Слой поиска (абстракции + провайдеры)
│   │   ├── base.py               # ABC: EmbeddingProvider, RerankerProvider; dataclasses: SearchChunk, EvidenceChunk
│   │   ├── opensearch_client.py  # OpenSearch: index bootstrap, BM25 search, bulk indexing, highlight, synonyms
│   │   ├── qdrant_client.py      # Qdrant: collection management, vector upsert, similarity search with filters
│   │   ├── embeddings.py         # Embedding providers: OpenAI text-embedding-3-small / custom
│   │   ├── reranker.py           # Reranker providers: Local HTTP, Cohere, Custom (no-op fallback)
│   │   └── __init__.py
│   │
│   ├── services/                 # Бизнес-логика (RAG pipeline, ingestion, config)
│   │   ├── orchestrator.py       # State machine: OrchestratorContext, OrchestratorAction, next_action(), run()
│   │   ├── answer_service.py     # AnswerService — реализация OrchestratorHandlers protocol; точка входа в RAG
│   │   ├── schemas.py            # Dataclass-контракты: QuerySpec, RetrievalPlan, EvidenceSet, DecisionResult, etc.
│   │   ├── normalizer.py         # LLM-нормализатор запроса → QuerySpec (intent, evidence, hypotheses, slots)
│   │   ├── retrieval.py          # RetrievalService: BM25+vector parallel fetch, RRF fusion, rerank, evidence selector
│   │   ├── retrieval_planner.py  # Построение RetrievalPlan из QuerySpec/retry_strategy (profile, doc_types, weights)
│   │   ├── retry_planner.py      # RetryStrategy: boost patterns, doc_type filters, suggested_query для retry
│   │   ├── evidence_set_builder.py  # EvidenceSet из CandidatePool (coverage, trust_mix, diversity)
│   │   ├── evidence_selector.py  # LLM-based coverage-aware evidence selection
│   │   ├── evidence_quality.py   # LLM evidence quality gate (sufficiency, completeness, actionability)
│   │   ├── evidence_evaluator.py # LLM оценка релевантности evidence → advises Retry Planner
│   │   ├── evidence_hygiene.py   # Telemetry: boilerplate, URL coverage, content density (regex-based signals)
│   │   ├── decision_router.py    # Deterministic routing: ASK_USER/ESCALATE/PASS based on QuerySpec + quality
│   │   ├── reviewer.py           # ReviewerGate: claim-level review, AnswerCalibrator, trim/downgrade/escalate
│   │   ├── claim_parser.py       # Claim segmentation, risk classification (policy/number/risky claims)
│   │   ├── self_critic.py        # LLM self-critic после генерации → regenerate on fail
│   │   ├── final_polish.py       # LLM final polish (clarity, structure, tone)
│   │   ├── query_rewriter.py     # LLM query rewriting when QuerySpec absent (cached in Redis)
│   │   ├── output_builder.py     # build_output(): DONE/ASK_USER/ESCALATE → AnswerOutput с debug payload
│   │   ├── answer_utils.py       # Helpers: format_evidence_for_prompt, parse_llm_response, answer_plan, calibration
│   │   ├── flow_debug.py         # Pipeline logging (_pipeline_log), build_flow_debug() для debug payload
│   │   ├── conversation_context.py  # Truncation: truncate_for_pipeline, truncate_for_prompt (history limits)
│   │   ├── language_detect.py    # Non-LLM language detection (archi_v3)
│   │   ├── intent_cache.py       # Predefined answers for common intents (who am i, what can you do)
│   │   ├── ingestion.py          # IngestionService: clean HTML, semantic chunking, embed, index (OpenSearch+Qdrant)
│   │   ├── doc_type_service.py   # DocType catalog cache from DB (CRUD via admin)
│   │   ├── doc_type_classifier.py  # LLM classification crawled docs (policy/tos/faq/howto/pricing/other)
│   │   ├── doc_type_router.py    # Doc type routing for retrieval (keyword heuristics or LLM)
│   │   ├── branding_config.py    # System prompt, intents, branding cache from DB (AppConfig)
│   │   ├── branding_auto_generator.py  # LLM auto-generate branding (system prompt, fallback messages)
│   │   ├── llm_config.py         # LLM config cache from DB (model, fallback, api_key, base_url)
│   │   ├── llm_gateway.py        # LLMGateway ABC + OpenAIGateway: chat(), Redis cache, fallback model, token budget
│   │   ├── model_router.py       # Task-aware routing: primary (gpt-5.2) for generate/self_critic, economy for rest
│   │   ├── archi_config.py       # Feature flags from DB (app_config) with env fallback: 13 toggles
│   │   ├── auth_service.py       # JWT encode/decode, bcrypt password verify, API token validation (DB)
│   │   ├── source_sync.py        # Reverse-sync DB changes → source JSON files (per doc_type)
│   │   ├── source_loaders.py     # Load documents from source JSON files, taxonomy metadata enrichment
│   │   ├── ticket_sync.py        # Sync approved tickets → source file for ingestion
│   │   ├── ticket_db.py          # Ticket CRUD helpers
│   │   ├── ticket_loaders.py     # Load tickets from source files
│   │   ├── url_fetcher.py        # Fetch URL content (httpx), extract title/text/links
│   │   ├── web_crawler.py        # Website crawler (BFS, max_pages, max_depth, exclude_prefixes)
│   │   ├── file_parser.py        # File parsing for ingestion (txt, md, html)
│   │   ├── offline_eval.py       # Offline evaluation runner (golden set, metrics)
│   │   ├── __init__.py
│   │   │
│   │   └── phases/               # Фазы RAG-пайплайна (вызываются оркестратором)
│   │       ├── retrieve.py       # RETRIEVE: retrieval + evidence hygiene + evidence evaluator (parallel)
│   │       ├── assess.py         # ASSESS_EVIDENCE: quality gate (LLM v2 or rule-based)
│   │       ├── decide.py         # DECIDE: decision router (deterministic lane assignment)
│   │       ├── generate.py       # GENERATE: LLM answer generation + reasoning prepass + self-critic
│   │       ├── verify.py         # VERIFY: reviewer gate (claim-level review, hypothesis judge)
│   │       ├── relevance_check.py  # Conversation history relevance check before generate
│   │       └── __init__.py
│   │
│   ├── crawlers/                 # Внешние краулеры
│   │   ├── whmcs.py              # WHMCS ticket crawler (Playwright browser automation)
│   │   └── __init__.py
│   │
│   └── __init__.py
│
├── worker/                       # Celery worker для async ingestion
│   ├── celery_app.py             # Celery app config (Redis broker)
│   ├── tasks.py                  # ingest_documents_task — async ingestion в sync context
│   └── __init__.py
│
├── frontend/                     # React + Vite SPA (админ-панель + chat UI)
│   ├── src/
│   │   ├── pages/                # 14 страниц: Dashboard, ConversationList/Detail, DocumentList/Detail,
│   │   │                         #   Crawler, Settings, Login, ApiReference, ApiTokens, TicketList/Detail,
│   │   │                         #   IntentList, DocTypeList
│   │   ├── api/                  # API client layer (axios)
│   │   ├── contexts/             # React contexts (auth, config)
│   │   ├── App.tsx               # Router + layout
│   │   └── main.tsx              # Entry point
│   ├── package.json              # React 19, Vite 7, Tailwind 4, axios, react-router-dom 7
│   ├── Dockerfile
│   └── nginx.conf
│
├── tests/                        # Test suite (pytest, pytest-asyncio)
│   ├── conftest.py               # Fixtures: mock LLM, mock retrieval, test DB
│   ├── test_orchestrator.py      # State machine transitions, terminal actions
│   ├── test_answer_service.py    # End-to-end RAG pipeline tests
│   ├── test_retrieval.py         # Hybrid retrieval, RRF, rerank
│   ├── test_normalizer.py        # QuerySpec normalization (LLM mock)
│   ├── test_reviewer.py          # Reviewer gate, claim-level trim, calibration
│   ├── test_evidence_quality.py  # Quality gate (LLM + rule-based)
│   ├── test_evidence_selector.py # LLM evidence selection
│   ├── test_decision_router.py   # Deterministic routing
│   ├── test_self_critic.py       # Self-critic regenerate
│   ├── test_rag_integration.py   # Full pipeline integration
│   ├── test_model_router.py      # Task-aware model routing
│   ├── test_llm_gateway.py       # LLM gateway cache, fallback
│   ├── test_query_rewriter.py    # Query rewriting + cache
│   ├── test_claim_parser.py      # Claim segmentation
│   ├── test_evidence_set_builder.py
│   ├── test_retrieval_planner.py
│   ├── test_evidence_hygiene.py  # (if exists)
│   ├── test_offline_eval.py
│   ├── test_output_builder.py
│   ├── test_flow_debug.py
│   ├── test_phase_verify.py
│   ├── test_phase_generate.py
│   ├── test_relevance_check.py
│   ├── test_rate_limit.py
│   ├── test_branding_config.py
│   ├── test_source_loaders.py
│   ├── test_url_fetcher_links.py
│   ├── test_opensearch_client_phase2.py
│   ├── test_ingestion_chunking_phase2.py
│   └── __init__.py
│
├── scripts/                      # CLI утилиты
│   ├── init_db.py                # Database initialization
│   ├── create_admin_user.py      # Create admin user (make create-admin)
│   ├── ingest_from_source.py     # Bulk ingest from source JSON files
│   ├── ingest_tickets_from_source.py
│   ├── crawl_whmcs_tickets.py    # WHMCS crawler CLI
│   ├── reingest_all.py           # Re-ingest all documents
│   ├── run_offline_eval.py       # Run offline evaluation
│   ├── build_offline_eval_golden_set.py
│   ├── debug_retrieval_zero_chunks.py  # Debug: why retrieval returns 0 chunks
│   ├── debug_retrieval_ip.py
│   ├── debug_qdrant.py
│   ├── debug_chunks_by_url.py
│   ├── debug_normalizer.py
│   ├── debug_search_open_ticket.py
│   ├── delete_noti_tickets.py
│   ├── import_whmcs_sql_dump_to_tickets.py
│   ├── add_python_strings_to_whmcs_sql.py
│   ├── whmcs_login_browser.py
│   └── test_yescale_api.py
│
├── alembic/                      # Database migrations (Alembic)
│   ├── env.py
│   ├── script.py.mako
│   └── versions/                 # 11 migrations (001–011)
│       ├── 001_initial_schema.py
│       ├── 002_add_documents_metadata_source_file.py
│       ├── 003_drop_external_user_id.py
│       ├── 004_add_message_debug_metadata.py
│       ├── 005_add_conversation_source_ticket_livechat.py
│       ├── 006_add_app_config_and_intents.py
│       ├── 007_add_tickets_table.py
│       ├── 008_add_ticket_approval_status.py
│       ├── 009_seed_llm_config.py
│       ├── 010_add_doc_types_table.py
│       └── 011_add_users_and_api_tokens.py
│
├── nginx/                        # Nginx reverse proxy config (full deployment profile)
│   └── nginx.conf
│
├── source/                       # Source JSON files for ingestion (mounted volume)
│
├── .cursor/rules/                # AI agent rules (project-development.mdc)
├── .env.example                  # Environment variable template
├── pyproject.toml                # Python project config (deps, pytest)
├── requirements.txt              # Pip requirements
├── Dockerfile                    # Production image (Playwright, Python)
├── Dockerfile.dev                # Dev image
├── docker-compose.yml            # Full stack: api, worker, postgres, redis, opensearch, qdrant, minio, frontend, nginx
├── docker-compose.dev.yml        # Dev compose (hot reload)
├── docker-entrypoint.sh          # Container entrypoint (migrations, playwright install)
├── Makefile                      # Dev commands: make dev, make test, make create-admin, etc.
├── alembic.ini                   # Alembic config
├── CHANGELOG.md
├── README.md
└── main.py                       # Empty (entry point is app/main.py)
```

## Внешние зависимости и их роль

| Зависимость | Роль | Конфиг env |
|---|---|---|
| **PostgreSQL 15** | Primary OLTP DB: documents, chunks, conversations, messages, citations, users, tickets, app_config, intents, doc_types, audit_llm_calls, eval_cases | `DATABASE_URL` |
| **Redis 7** | Rate limiting (token bucket), LLM response cache, query rewriter cache, Celery broker | `REDIS_URL`, `CELERY_BROKER_URL` |
| **OpenSearch 2.11** | BM25 full-text search index (hybrid retrieval). Synonyms, stemmers, highlighting | `OPENSEARCH_HOST` |
| **Qdrant 1.12** | Vector similarity search (cosine). Фильтрация по doc_type, page_kind, product_family | `QDRANT_HOST`, `QDRANT_PORT` |
| **MinIO (S3)** | Object storage для raw document content (опционально) | `OBJECT_STORAGE_URL` |
| **OpenAI API** | LLM (gpt-5.2 primary, gpt-4o-mini economy, gpt-3.5-turbo fallback) + embeddings (text-embedding-3-small) | `OPENAI_API_KEY`, `LLM_MODEL` |
| **Cohere API** | Опциональный reranker provider | `COHERE_API_KEY` |
| **Local Reranker** | Опциональный self-hosted cross-encoder reranker (HTTP service) | `RERANKER_URL` |
| **Celery** | Async task queue для ingestion (bulk document processing) | `CELERY_BROKER_URL` |
| **Playwright** | Browser automation для WHMCS ticket crawling | `PLAYWRIGHT_BROWSERS_PATH` |
| **OpenTelemetry** | Distributed tracing + Prometheus metrics export | — |
