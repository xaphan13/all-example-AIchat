# Отправка запросов в OpenRouter и подобные агрегаторы: переносимый пример чата

> Дата: 21.09.2026
> Код: `openrouter_chat_example` — запускается и копируется в другой проект
> Часть цикла: Часть 1 — инвентаризация проектов, Часть 2 — обзор библиотек,
> Часть 3 — надёжность и практика; этот документ — пример реализации целиком.

## 1. Что здесь собрано

Готовый пример чата к **OpenAI-совместимому агрегатору**: OpenRouter из коробки,
любой аналог (LiteLLM Proxy, Portkey, YesScale, Together, self-hosted шлюз) — сменой
адреса. Цель — перенос: один контракт, две реализации за ним, без привязки к фреймворку.

```
examples/openrouter_chat_example/
├── chat.py             # контракт: интерфейс, модели данных, ошибка, фабрика
├── httpx_client.py     # реализация на httpx — видно весь протокол
├── openai_client.py    # реализация на официальном SDK OpenAI
├── config.py           # пример чтения настроек (ключ, адрес, модель, fallback)
├── example_usage.py    # три сценария: один ответ, стриминг, fallback-модели
├── requirements.txt
└── README.md           # англоязычная версия этого материала
```

Ключевая идея переносимости: **приложение знает только `ChatClient`**. Меняется
библиотека доступа — меняется одна ветка фабрики `create_client(...)`, остальной код
(роуты FastAPI, сервисный слой, агенты) не трогается.

---

## 2. Контракт: два метода и честные ошибки

```python
# chat.py
class ChatClient(ABC):
    @abstractmethod
    async def chat(self, messages: list[ChatMessage], *, model: str,
                   temperature: float = 0.7, max_tokens: int = 1024) -> ChatResult:
        """Один запрос — один полный ответ."""

    @abstractmethod
    async def stream(self, messages: list[ChatMessage], *, model: str,
                     temperature: float = 0.7, max_tokens: int = 1024) -> AsyncIterator[str]:
        """Один запрос — поток текстовых фрагментов по мере генерации."""

    @abstractmethod
    async def aclose(self) -> None:
        """Закрыть соединения. Клиент создаётся один раз на процесс."""
```

Плюс `stream_with_usage(...)` — поток, последним элементом которого идёт `Usage`.
Он не абстрактный: базовая реализация просто не отдаёт расход, а умеющие —
переопределяют.

Модели данных — `ChatMessage`, `ChatResult`, `Usage` — плоские датаклассы.
`ChatResult` несёт не только текст, но и то, что нужно продакшену: имя реально
ответившей модели, расход токенов, выбранного агрегатором провайдера, `finish_reason`.

**Ошибки не глотаются.** Вместо `except Exception: return None` (как в
`llm-council-karpathy`) контракт требует `ProviderError` с тремя полезными полями:

```python
class ProviderError(RuntimeError):
    def __init__(self, message, *, status_code=None, model=None, retryable=False):
        ...
```

`retryable` — ключ к осмысленной деградации: решение «повторить / сменить модель /
показать ошибку» принимает вызывающий код, а не слой доступа.

---

## 3. Реализация на httpx: протокол как он есть

Полный цикл запроса вручную, без SDK. Заголовки — с атрибуцией агрегатора:

```python
@staticmethod
def _headers(app_url: str, app_title: str) -> dict[str, str]:
    return {
        "Content-Type": "application/json",
        "HTTP-Referer": app_url,     # атрибуция приложения в статистике
        "X-Title": app_title,        # имя приложения в статистике
    }
```

Клиент создаётся **один раз** и переиспользует соединения — в отличие от
`llm-council-karpathy`, где новый `AsyncClient` создаётся на каждый вызов:

```python
self._client = httpx.AsyncClient(
    base_url=self._base_url,
    timeout=httpx.Timeout(timeout_seconds, connect=5.0, read=timeout_seconds),
    headers=self._headers(app_url, app_title),
)
```

Таймаут дифференцирован: `connect` — короткий, `read` — на паузу между чанками
стрима, общий — на весь запрос.

### Повторы с уважением к `Retry-After`

```python
RETRYABLE_STATUS_CODES = frozenset({408, 409, 425, 429, 500, 502, 503, 504})

for attempt in range(1, self._max_retries + 2):
    ...  # один POST
    if response.status_code < 400:
        return response
    last_error = ProviderError(..., retryable=response.status_code in RETRYABLE_STATUS_CODES)
    if not last_error.retryable:
        raise last_error          # 400/401/422 повторять бессмысленно
    retry_after = self._retry_after_seconds(response)   # агрегатор сам сказал, сколько ждать
    if retry_after is not None:
        await asyncio.sleep(retry_after)
        continue
    delay = self._retry_backoff * (2 ** (attempt - 1))  # экспоненциальный backoff
    await asyncio.sleep(delay)
```

Главное различие с репозиторием: там повторов нет нигде, кроме RAG-чатбота, где
backoff **линейный** (`backoff_ms * attempt`). Здесь — экспоненциальный и с оглядкой
на подсказку сервера.

### Стриминг: две тонкости агрегаторов

```python
async with self._client.stream("POST", "/chat/completions", json=payload) as response:
    async for line in response.aiter_lines():
        chunk = self._parse_sse_line(line)      # None для пустых строк и [DONE]
        if chunk.get("usage"):                  # usage приходит ровно один раз
            final_usage = Usage(...)
        for choice in chunk.get("choices") or []:
            text = (choice.get("delta") or {}).get("content")
            if text:
                emitted_text = True
                yield text
```

Тонкость первая: у OpenRouter usage приходит **в последнем чанке перед `[DONE]`**,
и этот чанк содержит непустой `choices` (в отличие от спецификации OpenAI) — поэтому
он не отбрасывается, а разбирается на общих основаниях.

Тонкость вторая: **прерванный стрим не переигрывается, если текст уже ушёл клиенту** —
иначе пользователь увидит дубли. Отсюда флаг `emitted_text` в условии повтора:

```python
if emitted_text or not error.retryable or retries_left <= 0:
    raise
```

---

## 4. Реализация на официальном SDK: та же семантика, меньше кода

```python
self._client = AsyncOpenAI(
    api_key=api_key,
    base_url=base_url.rstrip("/"),
    default_headers={"HTTP-Referer": app_url, "X-Title": app_title},
    timeout=timeout_seconds,
    max_retries=max_retries,
)
```

Здесь два важных решения:

1. **Заголовки атрибуции заданы через `default_headers`** — то, чего нет ни в
   `llm-council-karpathy`, ни в Quorum. Устанавливаются один раз на клиент.
2. **Своего цикла повторов нет.** SDK сам повторяет 2 раза с экспоненциальным
   backoff на 408/409/429/5xx и сетевые ошибки. Ретраи должны жить на одном уровне —
   иначе попытки перемножаются.

Приведение ошибок к общему типу:

```python
def _as_provider_error(error: Exception, model: str) -> ProviderError:
    if isinstance(error, APIStatusError):
        return ProviderError(..., status_code=error.status_code, model=model,
                             retryable=error.status_code in RETRYABLE_STATUS_CODES)
    if isinstance(error, APITimeoutError):
        return ProviderError(..., model=model, retryable=True)
    return ProviderError(..., model=model, retryable=True)
```

Для получения расхода в стриме добавлен `stream_options={"include_usage": True}`:

```python
stream = await self._client.chat.completions.create(
    ..., stream=True, stream_options={"include_usage": True},
)
async for chunk in stream:
    if chunk.usage is not None:           # чанк с usage может быть без choices
        yield Usage(chunk.usage.prompt_tokens or 0, chunk.usage.completion_tokens or 0)
    for choice in chunk.choices or []:
        if choice.delta.content:
            yield choice.delta.content
```

---

## 5. Фабрика: единственная точка расширения

```python
def create_client(backend: str, *, api_key: str, base_url: str, **kwargs) -> ChatClient:
    if backend == "httpx":
        from .httpx_client import HttpxChatClient
        return HttpxChatClient(api_key=api_key, base_url=base_url, **kwargs)
    if backend == "openai":
        from .openai_client import OpenAISDKChatClient
        return OpenAISDKChatClient(api_key=api_key, base_url=base_url, **kwargs)
    raise ValueError(f"Неизвестная реализация клиента: {backend!r}. Доступны: 'httpx', 'openai'.")
```

Импорты ленивые: если проекту нужна одна библиотека, вторая не подтягивается.
Добавить третью реализацию (например, официальный SDK OpenRouter
`pip install openrouter` или LiteLLM) — это дописать ветку и не тронуть остальное.

---

## 6. Пример использования: три сценария

```python
settings = Settings.from_env()

# 1. Один запрос — один ответ
result = await ask_once(settings, question)
print(result.content, result.usage.total_tokens)

# 2. Стриминг с расходом токенов
await ask_streaming(settings, question)

# 3. Деградация: основная модель, затем резервные
chain = (settings.model, *settings.fallback_models)
for model in chain:
    try:
        return await client.chat(messages, model=model, ...)
    except ProviderError as error:
        if not error.retryable:
            raise              # 400 — это ошибка запроса, менять модель нет смысла
```

Третий сценарий показывает правильную семантику fallback: **переход на резервную
модель только на повторяемых отказах**. Ошибка запроса (400, 401, 422) должна
всплывать наверх, а не маскироваться сменой модели.

---

## 7. Перенос в другой проект

1. Скопировать `chat.py` и нужную реализацию (`httpx_client.py` и/или
   `openai_client.py`).
2. `config.py` заменить на свой источник настроек — код клиента не знает, откуда
   берутся ключ и адрес (у вас это может быть pydantic-settings, БД как в
   RAG-чатботе, секрет-менеджер).
3. Вызов `create_client(...)` оставить как есть; новая реализация — новая ветка.
4. `example_usage.py` не переносить — это демонстрация.

### Интеграция во FastAPI (пример)

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request

@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = Settings.from_env()
    app.state.chat = create_client(
        settings.backend, api_key=settings.api_key, base_url=settings.base_url,
        app_url=settings.app_url, app_title=settings.app_title,
        timeout_seconds=settings.timeout_seconds, max_retries=settings.max_retries,
    )
    yield
    await app.state.chat.aclose()          # один клиент на процесс, закрытие на выходе

app = FastAPI(lifespan=lifespan)

@app.post("/api/chat")
async def chat(request: Request, body: ChatRequest):
    client: ChatClient = request.app.state.chat
    result = await client.chat(
        [ChatMessage(role="user", content=body.message)], model=body.model,
    )
    return {"answer": result.content, "tokens": result.usage.total_tokens}
```

---

## 8. Что осталось за рамками примера

- **`provider`-объект агрегатора** (`order`, `allow_fallbacks`, `require_parameters`,
  `data_collection`) не используется ради краткости. Для OpenAI SDK он передаётся
  через `extra_body={"provider": {...}}`, для httpx — лишним ключом в теле. Если
  полагаетесь на tool calling или structured output, `require_parameters: true`
  обязателен: без него запрос может молча деградировать на провайдера, который
  этого не умеет.
- **Массив `models`** у OpenRouter (встроенный fallback на стороне агрегатора) —
  альтернатива ручной цепочке из сценария 3.
- **Подсчёт стоимости** — в примере есть только `Usage`; цены и калькуляция
  вынесены за скобки, потому что источник цен у каждого свой.
- **Prompt caching, зондирование доступных моделей, ротация ключей** — темы
  Части 3, а не этого примера.

## 9. Сверка с репозиторием

Пример сознательно отличается от того, как это сделано в существующих проектах,
и именно в тех местах, которые были отмечены как слабые:

| Аспект | В репозитории | В примере |
|---|---|---|
| Заголовки `HTTP-Referer` / `X-Title` | нет нигде | заданы на клиенте, один раз |
| Переиспользование соединения | новый `AsyncClient` на вызов (llm-council) | один клиент на процесс |
| Таймауты | почти не заданы | дифференцированные, `connect`/`read`/общий |
| Повторы на 429/5xx | нет (кроме линейного в RAG) | экспоненциальный backoff + `Retry-After` |
| Повтор прерванного стрима | — | запрещён после первого отданного фрагмента |
| Ошибка провайдера | `return None` / текст в стрим | `ProviderError` со `status_code` и `retryable` |
| Fallback-модель | только в RAG-чатботе | сценарий с явной цепочкой и проверкой `retryable` |
| Расход токенов в стриме | не собирается | `include_usage` (SDK) / финальный чанк (httpx) |

### Связанные документы

| Документ | О чём |
|---|---|
| `aggregators_part1_project_inventory.md` | как устроен доступ к провайдерам в 6 проектах |
| `aggregators_part2_libraries_and_approaches.md` | обзор библиотек и способов доступа |
| `aggregators_part3_reliability_and_practice.md` | таймауты, ретраи, fallback, стоимость, безопасность |
