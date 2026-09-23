# Example: chat with an aggregator provider (OpenRouter and alike)

Minimal, portable example of talking to an **OpenAI-compatible aggregator** —
OpenRouter first, any similar service (LiteLLM proxy, Portkey, YesScale, Together,
self-hosted gateway) by changing the address only.

The goal is a piece of code you can **copy into another project**: one contract,
two implementations behind it, no framework lock-in.

## Files

| File | What it contains |
|---|---|
| `chat.py` | The contract: `ChatClient` interface, `ChatMessage`, `ChatResult`, `Usage`, `ProviderError`, and the `create_client(...)` factory |
| `httpx_client.py` | Implementation on `httpx`: raw request body, attribution headers, SSE parsing, retries on 429/5xx, `Retry-After` |
| `openai_client.py` | Implementation on the official OpenAI SDK with a substituted `base_url` |
| `config.py` | How settings are read (key, address, model, fallback chain, timeouts) |
| `example_usage.py` | Three scenarios: single answer, streaming, fallback models |

A Russian-language guide with the same material lives at
`../../report/aggregator_chat_code_example.md`.

## Requirements

- Python 3.10+
- `httpx` and/or `openai` (see `requirements.txt`)

## Run

```bash
export OPENROUTER_API_KEY=sk-or-...
python -m examples.openrouter_chat_example.example_usage
```

Pick the implementation:

```bash
CHAT_BACKEND=httpx    # default: raw HTTP, no SDK
CHAT_BACKEND=openai   # official OpenAI SDK over the same endpoint
```

## Environment variables

| Variable | Default | Meaning |
|---|---|---|
| `OPENROUTER_API_KEY` | — | Required. Aggregator key. Never keep it in source code |
| `OPENROUTER_BASE_URL` | `https://openrouter.ai/api/v1` | Aggregator endpoint. Change it for a different service |
| `OPENROUTER_MODEL` | `openai/gpt-4o-mini` | Model in `vendor/model` form |
| `OPENROUTER_FALLBACK_MODELS` | empty | Comma-separated reserve models, tried in order on retryable failures |
| `OPENROUTER_APP_URL` | `http://localhost` | `HTTP-Referer` value: app attribution in aggregator stats |
| `OPENROUTER_APP_TITLE` | `OpenRouter Chat Example` | `X-Title` value: app name in aggregator stats |
| `CHAT_BACKEND` | `httpx` | Which implementation to use |
| `CHAT_TIMEOUT_SECONDS` | `60` | Whole-request timeout; also the gap between stream chunks |
| `CHAT_MAX_RETRIES` | `3` | Retries on 429/5xx and network errors |
| `CHAT_RETRY_BACKOFF_SECONDS` | `0.5` | Base for exponential backoff |
| `CHAT_TEMPERATURE` | `0.7` | Sampling temperature |
| `CHAT_MAX_TOKENS` | `1024` | Cap on the answer length |

## Design decisions worth keeping

1. **The client is created once per process.** `AsyncClient`/`AsyncOpenAI` reuse
   connections; creating a client per request destroys the pool and TLS sessions.
   Call `aclose()` on shutdown.
2. **Retries live on one level only.** The OpenAI SDK already retries twice on
   429/5xx, so `openai_client.py` adds no retry loop. The `httpx` implementation
   implements retries itself. Doing both multiplies attempts and timeouts.
3. **A stream is not replayed once text has been emitted** — otherwise the user
   would see duplicated output. `httpx_client.py` tracks `emitted_text`.
4. **`Retry-After` is respected** when the aggregator sends it.
5. **Attribution headers are set once on the client**, not per request.
6. **Errors are not swallowed.** The client raises `ProviderError` with
   `status_code` and `retryable`; fallback/retry policy is the caller's decision.
7. **The provider object of the aggregator is not used here** for brevity, but it
   is the natural next step: `extra_body={"provider": {...}}` for the OpenAI SDK,
   or an extra key in the request body for `httpx`.

## Notes specific to aggregators

- Under one model name there can be **several providers**, each with its own
  parameter set. If you rely on tool calling or structured output, set
  `provider.require_parameters = true` — otherwise the request may silently
  degrade to a provider that does not support what you asked for.
- In a stream, usage arrives **exactly once**, in the last chunk before `[DONE]`,
  and that chunk contains a non-empty `choices` array (unlike the OpenAI spec).
  `httpx_client.py` handles this explicitly.
- Some models accept `max_completion_tokens`, others only `max_tokens`. If you
  switch models, keep an eye on this.

## Porting into another project

1. Copy `chat.py` and one implementation (`httpx_client.py` and/or
   `openai_client.py`).
2. Replace `config.py` with your own settings source — the client code does not
   care where the key and address come from.
3. Keep calling `create_client(...)`; add a branch there for a new provider.
4. Leave `example_usage.py` behind — it is only a demo.
