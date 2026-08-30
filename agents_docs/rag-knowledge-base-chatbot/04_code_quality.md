# 04 — Code Quality (Оценка качества кодовой базы)

## Общая оценка

Кодовая база демонстрирует **высокий уровень дисциплины и зрелости**: чёткое разделение слоёв, документированные контракты (dataclasses), protocol-based декомпозиция пайплайна, глубокий fallback-дизайн и явная конфигурируемость. Проект явно прошёл несколько итераций (archi v3, Workstreams 1/3/5, Phase 1-6 — следы в docstrings и нейминге) и содержит осознанные компромиссы.

**Оценки по критериям:**

| Критерий | Оценка (1-10) | Комментарий |
|---|---|---|
| Читаемость | 8.5 | Именование понятное, docstrings на месте, структура фазы → единая точка входа |
| Модульность | 9 | Фазы изолированы, search-layer абстрагирован, провайдеры заменяемы |
| Связность/сцепление | 7.5 | Оркестратор слабо связан через Protocol, но `schemas.py` растёт |
| DRY | 7 | Повторы в `build_output()` (3 ветки почти идентичны), fallback-логика дублируется |
| KISS | 7.5 | Есть переусложнённые участки (retrieval.py — 1200+ строк) |
| SOLID | 8 | SRP соблюдён, OCP через абстракции, но `AnswerService` — God Object |
| Тестируемость | 8.5 | Mock-friendly конструкторы, protocol handlers, `tests/conftest.py` fixtures |

## Соответствие стандартам

### SOLID

- **S (SRP)**: Соблюдён в основном — фазы (`phases/`), провайдеры (`search/`), middleware (`core/`) изолированы. Нарушения: `AnswerService` агрегирует 4 зависимости + оркестрацию; `output_builder.py` содержит рендеринг, polish, метрики и дебаг-сборку в одной функции.
- **O (OCP)**: Отлично — `LLMGateway`, `RerankerProvider`, `EmbeddingProvider` расширяемы без модификации. Config-driven feature flags.
- **L (LSP)**: Соблюдён — `OpenAIGateway`/`LocalRerankerProvider` корректно заменяют базовые.
- **I (ISP)**: `OrchestratorHandlers` protocol точечный. `QualityReport` — агрегат многих опциональных полей.
- **D (DIP)**: Хорошо — конструкторы принимают зависимости, но в `answer_service.generate()` и routes есть прямые `import` внутри функций (не нарушение, но не pure DI).

### DRY

Дублирование кода:
1. `build_output()` (`app/services/output_builder.py`) — 3 ветки (DONE/ESCALATE/ASK_USER) почти идентичны (по 60+ строк каждая, различаются 2-3 аргументами). → Extraction: helper `_build_debug_payload(ctx, **overrides)`.
2. Fallback-цепочки в `retrieval.py`: `_search_opensearch_safe` и `_search_qdrant_safe` повторяют паттерн (TypeError → relaxed → empty). → Обобщение через helper.
3. Config-кэши: `archi_config.py`, `branding_config.py`, `llm_config.py`, `doc_type_service.py` — одинаковый паттерн (DB load → TTL cache → refresh). → Общий `ConfigCache` base class.
4. `_sanitize_*` функции в `normalizer.py` — большая семья однотипных коерций.
5. Ручное создание Redis connection в каждом вызове `_get_cached`/`_set_cached`/rate limit — нет пула.

### KISS

Переусложнено:
- `retrieval.py` (1221+ строк, один класс) — максимальная функциональная плотность: планирование, калибровка, fusion, bundle'ы, stats.
- `retrieval_planner.py`, `retry_planner.py` — пересекающаяся логика (обе генерируют doc_types/boost/query).
- `normalizer.py` (1360+ строк) — ~45 приватных хелперов санitизации/инференции. Несмотря на «LLM-led» философию, сохранились rule-based ветки (availability-детекция `_looks_like_availability_query`, `_apply_config_overrides`).
- Множество legacy флагов: `decision_router_use_llm` помечен `[Deprecated]`, `chunk_filter_enabled` — `[Deprecated]`, `normalizer_use_llm` — `[Deprecated]`. Они поддерживаются «для совместимости» — мертвый вес.

## Технический долг и «запахи кода»

### Высокий приоритет

1. **God Objects / Большие файлы**:
   - `app/services/retrieval.py` (~1250 строк) — один класс со всей retrieval-логикой.
   - `app/services/normalizer.py` (~1370 строк) — модуль нормализации.
   - `app/services/reviewer.py` (~830 строк) — ReviewerGate + AnswerCalibrator + много приватных хелперов.
   - `app/services/output_builder.py` — дублирование веток.
   - `app/api/routes/admin.py` (~914 строк) — все admin endpoint'ы в одном файле.
   - `app/search/opensearch_client.py` (~585 строк).

2. **Функциональное пересечение**: `retrieval_planner.py` vs `retry_planner.py` vs `doc_type_router.py` — три места генерации doc_types/retrieval-стратегий.

3. **Скрытые обращения к внешним системам в hot path**: `llm_gateway._get_cached()`/`_set_cached()` создают новое Redis-соединение на каждый LLM call (`redis.from_url()` + `close()` в цикле).

4. **Rule-based fallback сохраняется рядом с LLM-путём**: `evidence_quality_use_llm`/`evidence_quality_llm_v2` — двойной путь качества; правило «No narrow rules» из `.cursor/rules` не всегда соблюдается (availability-эвристики, `_POLICY_QUERY_TERMS` и т.д.).

### Средний приоритет

5. **Проброс данных через `ctx.extra`**: `OrchestratorContext.extra: dict[str, Any]` — де-факто «грязная» структура для передачи `answer_candidate`, `llm_resp`, `messages`, `hypothesis_history`, `error`, `verify_targeted_retry_*` и др. Нет типизации, легко рассинхронизировать ключи.
6. **`ctx._last_reviewer_result`** — приватный атрибут на dataclass'е, используется как псевдо-состояние.
7. **Многочисленные `try/except: pass` вокруг `_pipeline_log`** (`from app.services.flow_debug import _pipeline_log` в 5+ местах) — асинхронная/синхронная контекстная зависимость.
8. **Повторяющаяся конструкция «safe wrapper»**: `_int_setting`/`_float_setting` в `retrieval.py` дублируют валидацию pydantic.
9. **Неоднородность импортов**: lazy imports внутри функций (для избежания циклов) чередуются с top-level импортами без конвенции.
10. **`evidence_quality.py` LLM-путь + `evidence_hygiene.py` regex-путь** — два разных механизма качества evidence.

### Низкий приоритет

11. **Legacy-флаги**: `fallback_llm_decides_enabled`, `chunk_filter_enabled`, `decision_router_use_llm`, `normalizer_use_llm` — deprecated, но остаются в Settings и коде.
12. **Магические строки**: `"conversation"`, `"pricing"`, `"policy"` doc_types встречаются в коде напрямую (не из конфига). Частично адресуется через `.cursor/rules`.
13. **Отсутствие схемы для `evidence_selector` coverage_map** — свободный `dict[str, str]`.
14. **`main.py` (корневой)** — пустой файл-заглушка (приложение в `app/main.py`). Путает структуру.
15. **Тесты с именами legacy-фаз**: `test_opensearch_client_phase2.py`, `test_ingestion_chunking_phase2.py` — следы исторических итераций.

## Безопасность и надёжность

### Безопасность (оценка: хорошо, с замечаниями)

- ✅ **WAF middleware** (`gateway.py`): regex-детекция injection/jailbreak/SQLi/template injection, блокировка по IP.
- ✅ **Guardrails** (`guardrails.py`): sanitization user input (replaces dangerous patterns, 10k chars cap), `check_injection()` на уровне API.
- ✅ **PII redaction** в логах (`redact_pii`, `safe_for_logging`).
- ✅ **API keys**: env-ключи сравниваются константно-время? — нет, `==` (замечание: timing attack поверх сети маловероятен, но bcrypt/constant-time для sk_* хэшей желателен).
- ✅ **Password**: bcrypt hash (`auth_service.py`), токены хранятся как hash, prefix отображается.
- ✅ **CORS** конфигурируем, docs скрываются в production.
- ⚠️ **JWT_SECRET default**: `"change-me-in-production"` — если деплой без env, секрет известен. Enforced в docker-compose (`JWT_SECRET:?must be set`), но локально dev-mode.
- ⚠️ **`.env` loading**: `Settings` читает `.env` из cwd — в production секреты должны приходить из env, не файла.
- ⚠️ **Rate limit fail-open** при недоступности Redis — приемлемо для dev, спорно для prod.
- ⚠️ **`redirect_uri`/SSRF**: `documents.fetch-from-url` и `crawl-website` позволяют обращаться к произвольным URL с сервера (SSRF-вектор). Нет валидации на внутренние адреса (localhost, 169.254.x.x, etc.).
- ⚠️ **OpenSearch security disabled** в docker-compose (`plugins.security.disabled=true`) — приемлемо для dev, критично в prod.
- ⚠️ **Прямой доступ к `/metrics`** без auth (если маршрут смонтирован) — утечка метрик.

### Надёжность (оценка: хорошо)

- ✅ **Graceful degradation**: многоуровневые fallback'и для каждого внешнего сервиса.
- ✅ **Timeout'ы**: `asyncio.wait_for` везде, где обращение к внешним сервисам (LLM 60s, OpenSearch/Qdrant 6s, embedding 8s).
- ✅ **Semaphores**: concurrency limits (24) для retrieval вызовов — защита от перегрузки.
- ✅ **Idempotent ingestion** по checksum; crash-safe благодаря транзакциям.
- ✅ **Celery per-doc try/except** — один упавший документ не блокирует пакет.
- ⚠️ **`asyncio.run()` в Celery-тасках** (`worker/tasks.py`): в long-lived sync worker каждый вызов создаёт новый event loop; при вложенных tasks (chunk embedding) — риск накопления незакрытых ресурсов. Для производственных нагрузок предпочтителен `asyncio.create_task` в общем loop worker'а или `trio`-совместимый worker.
- ⚠️ **Celery `redis.from_url` per call** — нет пула соединений.
- ⚠️ **`datetime.utcnow()`** deprecated в Python 3.12+ (модели `ingestion.py` line 314 использует `datetime.utcnow()` — будет удалено в 3.12/3.13).
- ⚠️ **Нет ретраев для DB connection** при старте (pool_pre_ping есть, но startup lifespan загружает config до ретраев).
- ⚠️ **`orchestrator.run()` — 50 итераций**: при некорректном состоянии возможен лишний цикл (защита есть, но неявная).

### Утечки ресурсов

- ✅ DB: `get_db()` закрывает сессию в finally; `db_session()` контекстный менеджер.
- ⚠️ Redis: `r.close()` вызывается вручную — при исключении между create и close возможна утечка (в rate_limit есть finally, в llm_gateway — нет).
- ⚠️ `asyncio.Task` в `_fetch_parallel_candidates` создаются без явного cancel при исключении (gather с `return_exceptions=True` защищает, но таски на «побежавшие» запросы не отменяются).
- ⚠️ Playwright browser instances — в `web_crawler.py` и `whmcs.py` должны закрываться в finally (нет полной гарантии на всех ветках).

### Валидация

- ✅ Pydantic-схемы на входе API.
- ✅ Санитизация LLM-вывода в `normalizer.py` (`_sanitize_*`, whitelist-подход для intents/evidence/answer types).
- ⚠️ `_extract_probable_json` — эвристика; возможны ложные срабатывания на не-JSON ответе LLM.
- ⚠️ `check_injection` — regex-based; обходится перефразированием (документированный компромисс для prompt injection).
- ✅ Индексные ограничения в модели: unique на source_url, external_id, token_hash; составные индексы.
