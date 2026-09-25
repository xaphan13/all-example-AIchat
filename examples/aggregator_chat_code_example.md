# Отправка запросов в OpenRouter и подобные агрегаторы: пример чата

> Дата: 24.09.2026
> Код: `examples/openrouter_chat_example` — запускается через `uv` и копируется в другой проект
> Часть цикла: Часть 1 — инвентаризация проектов, Часть 2 — обзор библиотек,
> Часть 3 — надёжность и практика; этот документ — разбор примера целиком.

## 1. Что здесь собрано

Пример чата к **OpenAI-совместимому агрегатору**: OpenRouter из коробки,
любой аналог (LiteLLM Proxy, Portkey, YesScale, Together, self-hosted шлюз) — сменой
адреса. Цель — показать принцип: один контракт, две реализации за ним, без привязки
к фреймворку. Это учебный пример, а не продакшен-библиотека.

```
examples/openrouter_chat_example/
├── chat.py             # контракт: интерфейс, модели данных, ошибка, фабрика
├── httpx_client.py     # реализация на httpx — видно весь протокол
├── openai_client.py    # реализация на официальном SDK OpenAI
├── config.py           # настройки на pydantic-settings (ключ, адрес, модель, fallback)
├── example_usage.py    # три сценария: один ответ, стриминг, fallback-модели
├── pyproject.toml      # зависимости для uv
├── .env.example        # шаблон переменных окружения
└── README.md           # краткая версия этого материала
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

Всего два метода плюс закрытие. Расход токенов в стриме намеренно не собирается:
это усложнило бы контракт (пришлось бы различать текст и `Usage` в одном потоке)
ради детали, которая к принципу устройства чата не относится.

Модели данных разные по природе, и это отражено в их типах:

- `ChatMessage` — **модель pydantic**. Это данные из внешнего мира: роль приходит
  из пользовательского ввода, и её лучше проверить до запроса, а не получить 400
  от провайдера.
- `Usage` и `ChatResult` — **датаклассы**. Это выходные данные, валидация им не
  нужна, а pydantic добавил бы вес без пользы.

`ChatResult` несёт не только текст, но и то, что нужно для работы с ответом:
имя реально ответившей модели, расход токенов, выбранного агрегатором провайдера,
`finish_reason`.

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

### Ошибки: один тип на все реализации

```python
RETRYABLE_STATUS_CODES = frozenset({408, 409, 425, 429, 500, 502, 503, 504})

@staticmethod
def _raise_for_status(response: httpx.Response) -> None:
    """Превратить HTTP-ошибку в `ProviderError` с признаком временности."""
    if response.status_code < 400:
        return
    raise ProviderError(
        f"Агрегатор вернул {response.status_code}: {response.text[:500]}",
        status_code=response.status_code,
        retryable=response.status_code in RETRYABLE_STATUS_CODES,
    )
```

Повторов здесь нет намеренно: клиент делает один запрос, а на временный отказ
реагирует вызывающий код (сценарий с fallback-моделями ниже). Так пример не
обрастает политикой повторов, `Retry-After` и экспоненциальным backoff — это темы
надёжности, а не принципа устройства чата (разбор — в
`aggregators_part3_reliability_and_practice.md`).

`retryable` при этом сохраняется: по нему вызывающий код решает, менять ли модель
(429/5xx) или показать ошибку (400/401/422).

### Стриминг: разбор SSE руками

```python
async with self._client.stream("POST", "/chat/completions", json=payload) as response:
    if response.status_code >= 400:
        body = (await response.aread()).decode("utf-8", "replace")
        raise ProviderError(...)            # включая retryable

    async for line in response.aiter_lines():
        chunk = self._parse_sse_line(line)  # None для пустых строк и [DONE]
        if chunk is None:
            continue
        for choice in chunk.get("choices") or []:
            text = (choice.get("delta") or {}).get("content")
            if text:
                yield text
```

Что видно из этого кода и полезно понять про агрегаторы:

- **`stream=True` меняет тип ответа**, а не только способ доставки: вместо одного
  JSON приходит поток строк SSE (`data: {...}`), который надо разбирать самому.
- **`[DONE]` — служебная строка**, как и пустые строки-разделители: `_parse_sse_line`
  возвращает для них `None`.
- **В стриме важен только `delta.content`** — накопление текста уже сделано за вас
  на стороне сервиса.
- Расход токенов в стриме здесь не собирается, потому что usage приходит в
  последнем чанке (у OpenRouter — перед `[DONE]`, и этот чанк, вопреки спецификации
  OpenAI, содержит непустой `choices`). Для продакшена это делается через
  `stream_options={"include_usage": True}` у SDK.

---

## 4. Реализация на официальном SDK: та же семантика, меньше кода

```python
self._client = AsyncOpenAI(
    api_key=api_key,
    base_url=base_url.rstrip("/"),
    # Заголовки атрибуции агрегатора: задаются один раз на весь клиент.
    default_headers={"HTTP-Referer": app_url, "X-Title": app_title},
    timeout=timeout_seconds,
)
```

Ключевое отличие от httpx-реализации: **заголовки атрибуции задаются через
`default_headers`** — то, чего нет ни в `llm-council-karpathy`, ни в Quorum.
Устанавливаются один раз на клиент, а не на каждый запрос.

Приведение `ChatMessage` к тому, что ждёт SDK, — обычный словарь:

```python
async def chat(self, messages, *, model, temperature=0.7, max_tokens=1024) -> ChatResult:
    response = await self._client.chat.completions.create(
        model=model,
        messages=[m.model_dump() for m in messages],
        temperature=temperature,
        max_completion_tokens=max_tokens,   # не max_tokens — см. ниже
    )
    ...
```

Два практических момента, которые стоит запомнить:

- **`max_tokens` и `max_completion_tokens` — разные параметры.** Разные модели
  принимают разные; httpx-клиент шлёт `max_tokens`, SDK-клиент —
  `max_completion_tokens`.
- **Повторы SDK и свой цикл несовместимы.** SDK сам повторяет запросы на 429/5xx
  и сетевые ошибки. Если добавить свой цикл, попытки перемножатся. Здесь повторов
  нет ни там, ни там — решение о смене модели принимает вызывающий код.

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
settings = Settings()          # pydantic-settings: .env + окружение
client = build_client(settings)  # один клиент на все сценарии
try:
    # 1. Один запрос — один ответ
    result = await ask_once(client, settings)
    print(result.content, result.usage.total_tokens)

    # 2. Стриминг
    await ask_streaming(client, settings)

    # 3. Деградация: основная модель, затем резервные
    for model in settings.fallback_chain:
        try:
            return await client.chat(messages, model=model, ...)
        except ProviderError as error:
            if not error.retryable:
                raise          # 400 — это ошибка запроса, менять модель нет смысла
finally:
    await client.aclose()
```

Сценарий fallback показывает правильную семантику: **переход на резервную модель
только на повторяемых отказах**. Ошибка запроса (400, 401, 422) должна всплывать
наверх, а не маскироваться сменой модели.

Порядок попыток задан свойством `Settings.fallback_chain` — основная модель плюс
резервные из `OPENROUTER_FALLBACK_MODELS` одним кортежем, чтобы не склеивать этот
список в двух местах.

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
    settings = Settings()
    app.state.chat = create_client(
        settings.backend, api_key=settings.api_key, base_url=settings.base_url,
        app_url=settings.app_url, app_title=settings.app_title,
        timeout_seconds=settings.timeout_seconds,
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

- **Повторы и `Retry-After`.** Клиент делает один запрос и поднимает `ProviderError`;
  политику повторов (сколько, с каким backoff, когда сдаваться) выбирает
  приложение. В примере её нет, чтобы не смешивать принцип устройства чата с
  надёжностью — разбор в `aggregators_part3_reliability_and_practice.md`.
- **`provider`-объект агрегатора** (`order`, `allow_fallbacks`, `require_parameters`,
  `data_collection`) не используется ради краткости. Для OpenAI SDK он передаётся
  через `extra_body={"provider": {...}}`, для httpx — лишним ключом в теле. Если
  полагаетесь на tool calling или structured output, `require_parameters: true`
  обязателен: без него запрос может молча деградировать на провайдера, который
  этого не умеет.
- **Массив `models`** у OpenRouter (встроенный fallback на стороне агрегатора) —
  альтернатива ручной цепочке из сценария 3.
- **Расход токенов в стриме** — usage приходит в последнем чанке; чтобы его
  собирать, у SDK есть `stream_options={"include_usage": True}`, у httpx — разбор
  финального чанка вручную. Здесь это опущено, потому что требует различать текст
  и `Usage` в одном потоке.
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
| Настройки | разбор окружения руками в каждом проекте | одна модель `pydantic-settings` с явными именами переменных |
| Стриминг | ручной разбор SSE в llm-council | тот же разбор, но за одним контрактом с `chat()` |
| Ошибка провайдера | `return None` / текст в стрим | `ProviderError` со `status_code` и `retryable` |
| Fallback-модель | только в RAG-чатботе | сценарий с явной цепочкой и проверкой `retryable` |
| Датаклассы vs pydantic | смешано | pydantic только на входных данных, датаклассы на выходных |

### Связанные документы

| Документ | О чём |
|---|---|
| `aggregators_part1_project_inventory.md` | как устроен доступ к провайдерам в 6 проектах |
| `aggregators_part2_libraries_and_approaches.md` | обзор библиотек и способов доступа |
| `aggregators_part3_reliability_and_practice.md` | таймауты, ретраи, fallback, стоимость, безопасность |
