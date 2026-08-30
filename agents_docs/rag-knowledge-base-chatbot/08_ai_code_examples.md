# 08 — Примеры кода: интеграция с AI-моделями

> Приложение к [07_ai_models_report.md](./07_ai_models_report.md). Все фрагменты взяты из реального кода репозитория и сокращены для читаемости; номера строк указаны по состоянию на дату отчёта.

## 1. Абстракция LLM-шлюза и фабрика провайдеров

Единая точка интеграции: абстрактный класс `LLMGateway` и фабрика, выбирающая реализацию по конфигу. Новая модель/провайдер добавляется реализацией одного метода `chat()`.

```python
# app/services/llm_gateway.py:31
class LLMGateway(ABC):
    """Abstract LLM gateway interface."""

    @abstractmethod
    async def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.1,
        **kwargs: Any,
    ) -> LLMResponse:
        """Send chat completion request."""
        pass


# app/services/llm_gateway.py:225
def get_llm_gateway() -> LLMGateway:
    """Factory for LLM gateway."""
    settings = get_settings()
    if settings.llm_provider == "openai":
        return OpenAIGateway()
    raise ValueError(f"Unknown LLM provider: {settings.llm_provider}")
```

Структурированный ответ шлюза — типизированный dataclass с учётом токенов и модели:

```python
# app/services/llm_gateway.py:18
@dataclass
class LLMResponse:
    content: str
    model: str
    provider: str
    input_tokens: int
    output_tokens: int
    finish_reason: str | None = None
    raw: dict[str, Any] | None = None
```

## 2. Сам вызов нейросети (Chat Completions)

`OpenAIGateway.chat()`: поиск в Redis-кэше → вызов API с fallback-цепочкой моделей → кэширование и метрики.

```python
# app/services/llm_gateway.py:66 (сокращено)
class OpenAIGateway(LLMGateway):
    def __init__(self) -> None:
        api_key = get_llm_api_key()          # из БД (app_config) или env
        base_url = get_llm_base_url()        # OpenAI-совместимый endpoint
        self._client = AsyncOpenAI(api_key=api_key, base_url=base_url or None,
                                   timeout=settings.llm_timeout_seconds)

    async def chat(self, messages, temperature=0.1, **kwargs) -> LLMResponse:
        model = kwargs.pop("model", None) or get_llm_model()
        models_to_try = [model, get_llm_fallback_model()]   # primary → fallback

        # 1) кэш: sha256(messages + model + temperature)
        cached = await self._get_cached(_cache_key(messages, model, temperature))
        if cached:
            return cached

        # 2) параметр лимита токенов зависит от семейства модели
        def _token_param(m: str) -> dict:
            if m.startswith("o1") or m.startswith("gpt-5"):
                return {"max_completion_tokens": max_tokens}
            return {"max_tokens": max_tokens}

        # 3) вызов API с перебором моделей цепочки
        for m in models_to_try:
            try:
                response = await self._client.chat.completions.create(
                    model=m,
                    messages=messages,
                    temperature=temperature,
                    **_token_param(m),
                    **extra_params,      # prompt_cache_key и др.
                )
                result = LLMResponse(content=response.choices[0].message.content or "",
                                     model=response.model, provider="openai", ...)
                await self._set_cached(request_cache_key, result)
                return result
            except Exception as e:
                if m == models_to_try[-1]:
                    raise
```

## 3. Маршрутизация моделей по задачам

Критичные роли работают на дорогой модели, вспомогательные — на дешёвой:

```python
# app/services/model_router.py (полностью, 27 строк)
TASK_PRIMARY = frozenset({"generate", "self_critic"})
TASK_ECONOMY = frozenset({
    "normalizer", "decision_router", "evidence_evaluator", "evidence_quality",
    "final_polish", "doc_type_classifier", "query_rewriter", "evidence_selector",
    "branding_auto_generator", "conversation_relevance_check",
})


def get_model_for_task(task: str) -> str:
    """Primary (gpt-5.2) for critical tasks, economy for rest."""
    if not get_llm_task_aware_routing_enabled():
        return get_llm_model()
    if task in TASK_PRIMARY:
        return get_llm_model()
    if task in TASK_ECONOMY:
        return get_llm_model_economy() or get_llm_fallback_model()
    return get_llm_model()
```

## 4. Пример роли: нормализатор запроса (JSON-контракт)

Системный промпт задаёт JSON-схему, модель возвращает структуру запроса, код санитизирует каждое поле через allow-list'ы:

```python
# app/services/normalizer.py:180 (фрагмент промпта)
NORMALIZER_SYSTEM_PROMPT = """You normalize a user's query for a support chatbot.

Return JSON ONLY (no markdown, no extra text). If unsure, use empty lists or null.

Schema:
{
  "canonical_query_en": "...",
  "entities": ["..."],
  "required_evidence": ["..."],
  "risk_level": "low|medium|high",
  "retrieval_profile": "pricing_profile|policy_profile|...",
  "keyword_queries": ["..."],
  "semantic_queries": ["..."],
  ...
}
"""

# app/services/normalizer.py:943 (вызов модели)
model = get_model_for_task("normalizer")          # economy-модель
llm = get_llm_gateway()
resp = await llm.chat(
    messages=[
        {"role": "system", "content": NORMALIZER_SYSTEM_PROMPT},
        {"role": "user", "content": user_content},   # запрос + контекст диалога
    ],
    temperature=0.0,
    model=model,
    max_tokens=512,
)
payload = json.loads(_extract_probable_json(resp.content))  # обрезка ```json``` и парсинг
risk_level = _sanitize_risk(payload.get("risk_level"))      # коерция в allow-list
```

## 5. Пример роли: генерация ответа с доказательствами

Фаза GENERATE собирает system prompt (Core+Domain+Custom из БД), историю диалога и блок evidence, затем вызывает primary-модель:

```python
# app/services/phases/generate.py:264 (сокращено)
model = orchestrator.get_model_for_query(ctx.query)         # → get_model_for_task("generate")
evidence_block = format_evidence_for_prompt(evidence, settings.llm_max_evidence_chars)

system_prompt = get_system_prompt()                          # слои Core + Domain + Custom
messages = [{"role": "system", "content": system_prompt}]
for msg in truncate_for_prompt(ctx.conversation_history):    # история диалога
    messages.append({"role": msg["role"], "content": msg["content"]})
messages.append({"role": "user", "content":
    f"User question: {ctx.effective_query}\n\nEvidence:\n{evidence_block}"})

llm_resp = await llm.chat(messages=messages,
                          temperature=settings.llm_temperature,   # 0.0
                          model=model)
parsed = parse_llm_response(llm_resp.content)               # JSON → decision/answer/citations
```

JSON-контракт, который обязана вернуть модель:

```python
# app/services/branding_config.py (OUTPUT_SCHEMA, вшивается в системный промпт)
"""
OUTPUT SCHEMA (JSON):
{
  "decision": "PASS" | "ASK_USER" | "ESCALATE",
  "answer": "your grounded answer",
  "followup_questions": ["..."],
  "citations": [{"chunk_id": "...", "source_url": "...", "doc_type": "..."}],
  "confidence": 0.0 to 1.0
}
"""
```

## 6. Разбор и защита от невалидного JSON

```python
# app/services/answer_utils.py:309 (сокращено)
def parse_llm_response(content: str) -> dict[str, Any]:
    text = content.strip()
    if "```json" in text:                      # снимаем markdown-ограждения
        match = re.search(r"```json\s*([\s\S]*?)\s*```", text)
        if match:
            text = match.group(1)
    try:
        payload = json.loads(text)
        return _normalize_parsed_payload(payload)
    except Exception:
        # fallback вместо падения: вежливый ASK_USER
        return _normalize_parsed_payload({
            "decision": "ASK_USER",
            "answer": "We had trouble formatting the response. Could you rephrase?",
            "citations": [], "confidence": 0.0,
        })
```

## 7. Пример роли: самокритик (LLM-as-judge)

Отдельная роль проверяет grounding и полноту ответа; при провале генерация повторяется с фидбеком:

```python
# app/services/self_critic.py:18 (фрагмент промпта)
SELF_CRITIC_PROMPT = """You are a quality reviewer for a support chatbot answer.
Output JSON only: {"pass": true, "issues": [], "suggested_fix": ""}
Set pass=false if any of these are true:
- Unsupported claims or hallucinations
- Missing critical evidence-backed facts
- Incomplete option coverage..."""

# вызов и использование результата (app/services/phases/generate.py:325, сокращено)
critique_result = await self_critic(ctx.effective_query, answer, citations, ctx.evidence)
if critique_result and not critique_result.pass_:
    feedback = f"Previous attempt had issues: {', '.join(critique_result.issues[:2])}. " \
               f"Fix: {critique_result.suggested_fix}"
    messages[-1]["content"] += feedback
    llm_resp = await llm.chat(messages=messages, temperature=settings.llm_temperature, model=model)
```

## 8. Embeddings API

```python
# app/search/embeddings.py:25
class OpenAIEmbeddingProvider(EmbeddingProvider):
    async def embed(self, texts: list[str]) -> list[list[float]]:
        response = await self._client.embeddings.create(
            model=self._settings.embedding_model,   # text-embedding-3-small
            input=texts,
        )
        return [d.embedding for d in response.data]  # векторы 1536 dim → Qdrant
```

Тот же клиент использует `api_key`/`base_url` из общей LLM-конфигурации (БД → env), поэтому embeddings автоматически следуют за сменой провайдера.

## 9. Реранкер (не чат, а отдельный ML-сервис)

```python
# app/search/reranker.py:64 (Cohere)
payload = {
    "model": "rerank-multilingual-v3.0",
    "query": query,
    "documents": [c.chunk_text for c in chunks],
    "top_n": top_k,
}
resp = await client.post("https://api.cohere.ai/v1/rerank",
                         json=payload,
                         headers={"Authorization": f"Bearer {cohere_api_key}"})

# app/search/reranker.py:19 (локальный cross-encoder)
resp = await client.post(f"{reranker_url}/rerank",
                         json={"query": query, "documents": [...], "top_k": top_k})
# при недоступности — graceful fallback на исходные scores
```

## 10. Смена модели/провайдера без редеплоя

Модель, ключ и `base_url` читаются из таблицы `app_config` (переопределяют env), кэш 60 секунд:

```python
# app/services/llm_config.py:39 (сокращено)
async def refresh_cache(session: AsyncSession) -> None:
    db_values = await _load_from_db(session)   # ключи: llm_model, llm_fallback_model,
    settings = get_settings()                  #        llm_api_key, llm_base_url
    _cache["llm_model"] = db_values.get("llm_model") or settings.llm_model
    _cache["llm_api_key"] = db_values.get("llm_api_key") or settings.openai_api_key
    _cache["llm_base_url"] = db_values.get("llm_base_url") or settings.openai_base_url
```

Обновление через Admin API: `PUT /v1/admin/config/llm` (`app/api/routes/admin.py:438`) — можно переключиться, например, на OpenRouter/локальный vLLM, задав `llm_base_url` и `llm_model`.

## 11. Stateless API для внешнего агента/интеграции

Готовая точка для использования приложения как «агента по базе знаний» из других систем:

```python
# app/api/routes/reply.py:22 (сокращено)
@router.post("/generate", response_model=SuggestReplyResponse)
async def generate_suggested_reply(body: SuggestReplyRequest, _auth=Depends(verify_api_key)):
    """Stateless, one-shot: тикет-система шлёт вопрос → получает ответ оператору."""
    query = sanitize_user_input(body.query)              # guardrails
    answer_svc = AnswerService()
    output = await answer_svc.generate(query=query,
                                       conversation_history=body.conversation_history,
                                       trace_id=get_trace_id())
    return SuggestReplyResponse(
        answer=output.answer,
        decision=output.decision,          # PASS / ASK_USER / ESCALATE — точка handoff
        citations=citations,               # источники
        confidence=output.confidence,
    )
```
