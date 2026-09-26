# Связь с LLM-провайдерами: паттерны, разбор кода репозитория и лучшие практики

> Дата: 25.09.2026
> Источники: код 6 проектов репозитория + `openrouter_chat_example` (пути сверены
> с рабочим деревом), официальная документация OpenAI Python SDK, LangChain (`langchain-openai`),
> OpenRouter, LiteLLM; статьи о resilience-паттернах для LLM (проверено 25.09.2026).
>
> **Оговорка о статусе.** Всё, что помечено «в репозитории», — фактический код. Разделы
> с рекомендациями — это паттерны и практики, которых в репозитории может не быть; они
> не выдаются за реализованное. Код примеров «как правильно» написан для отчёта и в
> репозитории не лежит.

---

## 0. Резюме

В репозитории на одном и том же вопросе — «как приложение говорит с LLM-провайдером» —
реализованы **семь разных подходов разной зрелости**: от глобального клиента на уровне
модуля и клиента-на-каждый-запрос до зрелого шлюза с fallback и кэшем.

Главные выводы:

1. **Клиент — один на процесс.** `AsyncOpenAI` / `httpx.AsyncClient` держат пул
   соединений; создание клиента на каждый запрос убивает keep-alive и заставляет делать
   TLS-handshake заново (актуально для `openai-responses-python-quickstart` и
   `llm-council-karpathy`).
2. **Подключение к любому OpenAI-совместимому провайдеру — это `base_url` + `api_key`.**
   Это официальный и самый переносимый паттерн: OpenRouter, GitHub Models, vLLM, Ollama,
   LiteLLM Proxy, Azure OpenAI (v1 API) — все говорят на формате OpenAI.
3. **`langchain_openai.ChatOpenAI` официально нацелен только на API OpenAI.** Для
   OpenRouter/vLLM/DeepSeek документация LangChain рекомендует профильные пакеты
   (`ChatOpenRouter`, `ChatDeepSeek`): нестандартные поля ответов (например
   `reasoning_content`) `ChatOpenAI` не извлекает и не сохраняет.
4. **Ретраи и таймауты — двухуровневые.** SDK сам ретраит connection errors, 408, 409,
   429 и 5xx (по умолчанию 2 раза, backoff с джиттером) — но только их; 400/401/404 он
   не трогает, и правильно делает. Уровень выше — fallback-модель/провайдер, ещё выше —
   circuit breaker (только на системные сбои).
5. **Смена ключа/base_url в рантайме — отдельная инженерная задача** с гонками, если
   мутировать общий клиент (реальный пример гонки — `routers/files.py` в quickstart).
   Решения: пересоздание клиента с инвалидацией кеша (Quorum), `api_key`-коллбэк,
   `client.copy()` / `with_options()`.
6. **Синхронный SDK внутри async-приложения — антипаттерн** для стриминга:
   `asyncio.to_thread` на *создание* стрима не помогает, потому что итерация по чанкам
   остаётся синхронной и блокирует event loop (реальный пример — GroqStreamChain).
   Лекарство: нативный async-клиент (`AsyncGroq`, `AsyncOpenAI`).

---

## 1. Инвентаризация: как связь с провайдером сделана в репозитории

| Проект | Библиотека | Где создаётся клиент | Жизненный цикл | Провайдер |
|---|---|---|---|---|
| `AI-Chatbot` | `openai.AsyncOpenAI` | `app/services/chat.py:5` — глобальная переменная модуля | при импорте, навсегда | GitHub Models (`models.github.ai/inference/`) |
| `GroqStreamChain` | `groq.Groq` (sync) + `ChatGroq` | `services/llm_service.py` — поле `LLMService` | сервис-синглтон | Groq |
| `llm-council-karpathy` | `httpx` напрямую | `backend/openrouter.py:37` — `async with` **на каждый запрос** | один запрос | OpenRouter |
| `openai-responses-quickstart` | `openai.AsyncOpenAI` | `Depends(lambda: AsyncOpenAI())` в роутерах | **один HTTP-запрос** | OpenAI (Responses API) |
| `Quorum` | `langchain_openai.ChatOpenAI` | `backend/src/agents/base_agent.py:100` — лениво, с кешем | агент + кеш до смены ключа | OpenRouter через `base_url` |
| `rag-knowledge-base-chatbot` | `openai.AsyncOpenAI` | `app/services/llm_gateway.py:64`, `app/search/embeddings.py:23` | шлюз, создаётся фабрикой | OpenAI или любой совместимый (`base_url` из БД/env) |
| `openrouter_chat_example` | `httpx` **или** `openai.AsyncOpenAI` | фабрика `create_client(...)` в `chat.py` | один на процесс, `aclose()` | любой OpenAI-совместимый |

Плюс два «спутниковых» клиента для эмбеддингов: `Quorum/backend/src/infrastructure/database/vector_service.py:24`
и `../rag-knowledge-base-chatbot/app/search/embeddings.py` — оба тоже `AsyncOpenAI`.

Дальше — разбор каждого паттерна: код как есть, что хорошо, что плохо.

---

## 2. Семь паттернов из репозитория

### 2.1. Глобальный клиент-модуль (AI-Chatbot) — минимальный вариант

```python
# AI-Chatbot/app/services/chat.py — как в репозитории
from openai import AsyncOpenAI
from app.core.config import settings

client = AsyncOpenAI(
    api_key=settings.GITHUB_TOKEN,
    base_url="https://models.github.ai/inference/",
)

async def get_chat_response(prompt: str) -> str:
    message = (
        "Hey ChatGPT, you are a AI chatbot don not tell your name ..."
        + prompt
    )
    response = await client.chat.completions.create(
        model="openai/gpt-4o",
        messages=[{"role": "user", "content": message}],
    )
    return response.choices[0].message.content.strip() if response.choices else ""
```

**Что хорошо.** Клиент создаётся **один раз** при импорте модуля — пул соединений и
TLS-сессии переиспользуются. `base_url` подменён на GitHub Models — провайдер меняется
двумя аргументами конструктора, остальной код не меняется. Это и есть главный паттерн
всего отчёта в минимальном виде.

**Что плохо.**

- `base_url` и имя модели захардкожены строками, а не в настройках — смена провайдера
  требует правки кода.
- Нет `timeout` и `max_retries`: действуют дефолты SDK (600 секунд, 2 ретрая). Для
  web-запроса 600 секунд — это зависший пользователь.
- Ошибки не различаются: любой сбой провайдера — исключение наружу, а пустой `choices`
  молча превращается в `""` (пользователь получит «пустой ответ» вместо понятной ошибки).

**Минимальная правка того же подхода** (уровень «приемлемо для пет-проекта»):

```python
# Как можно улучшить, оставаясь в одном файле
from openai import AsyncOpenAI
from app.core.config import settings

client = AsyncOpenAI(
    api_key=settings.GITHUB_TOKEN,                       # ключ из env
    base_url=settings.LLM_BASE_URL,                      # https://models.github.ai/inference/
    timeout=30.0,          # общий таймаут запроса, а не 600
    max_retries=2,         # ретраи SDK: connection errors, 408/409/429/5xx
)

async def get_chat_response(prompt: str) -> str:
    response = await client.chat.completions.create(
        model=settings.LLM_MODEL,                        # "openai/gpt-4o"
        messages=[{"role": "user", "content": prompt}],
    )
    if not response.choices or not response.choices[0].message.content:
        raise RuntimeError("Провайдер вернул пустой ответ")
    return response.choices[0].message.content.strip()
```

> Пояснение. Пустой ответ — это ошибка интеграции, и её надо слышно ронять, а не
> возвращать `""`: иначе фронтенд покажет «успех» с пустым текстом, и диагностика
> превратится в гадание.

---

### 2.2. Нативный SDK провайдера + синхронный стрим в async (GroqStreamChain)

```python
# GroqStreamChain/services/llm_service.py — как в репозитории (сокращено)
from groq import Groq
from langchain_groq import ChatGroq

class LLMService:
    def __init__(self):
        self.client = Groq(api_key=GROQ_API_KEY)          # синхронный клиент
        self.langchain_client = ChatGroq(...)             # создаётся, но не используется

    async def generate_response_stream(self, messages):
        # ...
        completion = await asyncio.to_thread(
            self.client.chat.completions.create,
            model=MODEL_NAME, ...,
            stream=True,
        )
        for chunk in completion:              # ← синхронная итерация!
            content = chunk.choices[0].delta.content
            if content:
                yield content
```

**Что хорошо.** Клиент один на сервис (синглтон). `asyncio.to_thread` корректно
выполняет *блокирующий вызов* создания стрима в отдельном потоке.

**Что плохо.**

1. **`for chunk in completion` блокирует event loop.** `completion` — синхронный
   генератор: каждый `next()` — блокирующее чтение из сокета. Пока Groq генерирует
   ответ, *весь* FastAPI-процесс (все WebSocket-сессии, health-checks) стоит. Для
   чат-приложения это самый дорогой баг из всех, что есть в репозитории по теме отчёта.
2. `self.langchain_client = ChatGroq(...)` — мёртвый код: создаётся, но нигде не
   вызывается.
3. `messages.insert(0, system_message)` мутирует входящий список — при повторном
   вызове с тем же списком system prompt задублируется (это ограничение зафиксировано
   и в `../agents_docs/GroqStreamChain`).

**Правильный вариант — нативный async-клиент** (у Groq он есть, как и у OpenAI):

```python
from groq import AsyncGroq

class LLMService:
    def __init__(self):
        self.client = AsyncGroq(api_key=GROQ_API_KEY)    # async-версия

    async def generate_response_stream(self, messages: list[Message]):
        groq_messages = [{"role": "system", "content": SYSTEM_PROMPT, **...}]
        # в новый список, а не insert в чужой
        stream = await self.client.chat.completions.create(
            model=MODEL_NAME,
            messages=groq_messages,
            stream=True,
        )
        async for chunk in stream:                        # async-итерация — event loop свободен
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
```

> Пояснение. Правило: в async-приложении либо нативный async-SDK, либо синхронный SDK
> только для *нестриминговых* вызовов целиком через `asyncio.to_thread`. Смешанный
> вариант «async-обёртка вокруг синхронного генератора» не спасает.

---

### 2.3. httpx напрямую, клиент на каждый запрос (llm-council-karpathy)

```python
# llm-council-karpathy/backend/openrouter.py — как в репозитории (сокращено)
async def query_model(model: str, messages, timeout: float = 120.0):
    headers = {"Authorization": f"Bearer {OPENROUTER_API_KEY}", ...}
    payload = {"model": model, "messages": messages}
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:   # ← новый клиент на запрос
            response = await client.post(OPENROUTER_API_URL, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            message = data['choices'][0]['message']
            return {'content': message.get('content'), 'reasoning_details': message.get('reasoning_details')}
    except Exception as e:
        print(f"Error querying model {model}: {e}")                 # ← ошибка глотается
        return None

async def query_models_parallel(models, messages):
    tasks = [query_model(model, messages) for model in models]
    responses = await asyncio.gather(*tasks)                        # ← параллельность — правильно
    return dict(zip(models, responses))
```

**Что хорошо.** `asyncio.gather` — ровно тот инструмент для «совета моделей»: все
участники опрашиваются параллельно, суммарное время = времени самого медленного, а не
сумме. Ручной httpx даёт полный контроль над заголовками и телом. `return None` при
ошибке удобен как раз для gather: один упавший член совета не роняет стадию.

**Что плохо.**

1. **`httpx.AsyncClient` создаётся на каждый вызов.** У совета из 4 моделей на стадию 1
   — 4 клиента, на стадию 2 (рецензии) — ещё, и т.д. Каждый — новый пул, новый
   TLS-handshake (~50–300 мс лишних на соединение), никакого keep-alive между запросами.
2. `print` вместо логгера, `except Exception` — глотание всех ошибок, включая опечатки
   в коде.

**Правильный вариант — клиент один на процесс:**

```python
# Модуль-синглтон или lifespan-зависимость
import httpx

class OpenRouterClient:
    def __init__(self, api_key: str, timeout: float = 120.0):
        self._client = httpx.AsyncClient(
            base_url="https://openrouter.ai/api/v1",
            timeout=httpx.Timeout(timeout, connect=5.0),
            headers={"Authorization": f"Bearer {api_key}"},
        )

    async def query_model(self, model: str, messages: list[dict]) -> dict | None:
        try:
            response = await self._client.post(
                "/chat/completions",
                json={"model": model, "messages": messages},
            )
            response.raise_for_status()
            return response.json()["choices"][0]["message"]
        except httpx.HTTPStatusError as e:
            logger.warning("model_failed", model=model, status=e.response.status_code)
            return None          # один член совета упал — стадия жива
        except httpx.HTTPError as e:
            logger.warning("model_network_error", model=model, error=str(e))
            return None

    async def aclose(self) -> None:
        await self._client.aclose()
```

> Пояснение. `httpx.Timeout(120.0, connect=5.0)` разделяет «не смогли подключиться за 5
> секунд» (провайдер/сеть лежит — ретрай бессмыслен, быстро фейлимся) и «долго думает»
> (LLM — это нормально). Один и тот же пул соединений работает на все модели совета:
> 4 параллельных запроса переиспользуют keep-alive к одному хосту.

---

### 2.4. Клиент на каждый HTTP-запрос через Depends (openai-responses-quickstart)

```python
# openai-responses-python-quickstart/routers/chat.py — как в репозитории
from fastapi import Depends
from openai import AsyncOpenAI

@router.get("/receive")
async def stream_response(
    conversation_id: str,
    client: Annotated[AsyncOpenAI, Depends(lambda: AsyncOpenAI())]   # ← новый клиент на запрос
) -> StreamingResponse:
    ...
    stream = await client.responses.create(...)
```

Этот паттерн встречается в `routers/chat.py`, `routers/files.py`, `routers/setup.py`.

**Что хорошо (и почему авторы так сделали).** `AsyncOpenAI()` без аргументов читает
`OPENAI_API_KEY` из окружения **в момент создания**. Приложение имеет setup-флоу
(`/setup` пишет ключ и модель в `.env` на лету) — новый клиент на каждый запрос
гарантирует, что смена настроек подхватится без рестарта. Это осознанный компромисс.

**Что плохо.**

1. Новый `AsyncOpenAI` = новый `httpx.AsyncClient` = новый пул соединений на каждый
   запрос: TLS-handshake, нет keep-alive, лишняя латентность и нагрузка.
2. Клиент не закрывается явно (`await client.close()`) — полагается на GC; под
   нагрузкой копятся «unclosed client» предупреждения.
3. Там, где настройки реально меняются на лету, это решается дешевле (см. §7).

**Правильный вариант — lifespan + `with_options`:**

```python
# main.py — клиент живёт столько же, сколько приложение
from contextlib import asynccontextmanager
from openai import AsyncOpenAI

@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.openai = AsyncOpenAI()          # читает OPENAI_API_KEY один раз
    yield
    await app.state.openai.close()            # явное закрытие

app = FastAPI(lifespan=lifespan)

# роутер
def get_client(request: Request) -> AsyncOpenAI:
    return request.app.state.openai

@router.get("/receive")
async def stream_response(
    conversation_id: str,
    client: Annotated[AsyncOpenAI, Depends(get_client)],
) -> StreamingResponse:
    ...

# Если для отдельного запроса нужен свой timeout/ретраи — не пересоздаём клиент:
await client.with_options(timeout=30.0).responses.create(...)
```

> Пояснение. `with_options()` возвращает «копию» клиента с переопределёнными
> настройками, **разделяя** тот же httpx-пул. Это официальный механизм SDK для
> per-request настроек — вместо создания нового клиента.

---

### 2.5. Гонка при мутации общего клиента (quickstart, routers/files.py)

```python
# openai-responses-python-quickstart/routers/files.py:364-368 — как в репозитории
# base_url workaround because container file download is not supported
# in the Python client yet
client.base_url = f"https://api.openai.com/v1/containers/{container_id}"
# ... запросы ...
client.base_url = "https://api.openai.com/v1"
```

**Почему это баг.** `client` — общий (в данном роутере создаётся на запрос, но сам
приём — мутация поля живого клиента). Если два запроса перекрываются во времени, один
из них выполнится с `base_url`, который выставил другой: запрос «скачать файл из
контейнера A» уедет в контейнер B. Диагностика таких гонок мучительная, потому что
воспроизводятся они только под нагрузкой.

**Правильный вариант — `with_options` / `copy` / отдельный клиент:**

```python
# Вариант 1: with_options — разделяет пул, меняет только base_url
container_client = client.with_options(
    base_url=f"https://api.openai.com/v1/containers/{container_id}"
)
resp = await container_client.files.content(file_id)

# Вариант 2: copy() — полный новый клиент с переопределением (пул не разделяется,
# но и исходный клиент не тронут)
container_client = client.copy(base_url=f"https://api.openai.com/v1/containers/{container_id}")
```

> Пояснение. Общее правило: **клиент после создания иммутабелен**. Всё, что надо
> поменять per-request (timeout, base_url, заголовки) — через `with_options`, всё, что
> per-deployment (ключ, провайдер) — через пересоздание клиента с инвалидацией кеша
> (как в Quorum, §2.6).

---

### 2.6. ChatOpenAI с base_url + ленивая инициализация и смена ключей (Quorum)

```python
# Quorum/backend/src/agents/base_agent.py — как в репозитории (сокращено)
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

class BaseAgent:
    async def _initialize_chat_model(self, use_streaming_callback: bool = False):
        # 1. Кеш: для стриминга и не-стриминга — разные модели (разные коллбэки)
        if use_streaming_callback:
            if self._streaming_model_initialized and self._chat_model_streaming:
                return self._chat_model_streaming
        else:
            if self._model_initialized and self._chat_model:
                return self._chat_model

        # 2. Ключ берётся из settings service: сначала БД, потом env
        openrouter_key = await self._settings_service.get_openrouter_api_key()

        # 3. Tool-биндинги, если есть реестр инструментов
        tool_kwargs = {}
        if self._tool_registry and self._tool_registry.list_tools():
            tool_kwargs["tools"] = self._tool_registry.get_all_schemas()

        chat_model = ChatOpenAI(
            model=model_name,                       # напр. "anthropic/claude-3.5-sonnet"
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
            api_key=openrouter_key,
            base_url="https://openrouter.ai/api/v1",   # ← OpenRouter через ChatOpenAI
            callbacks=callbacks,                        # трекинг токенов
            **tool_kwargs
        )
        # ... кеширование модели
```

И смена ключей без рестарта:

```python
    async def refresh_api_keys(self):
        """Вызывается, когда ключ обновили в БД: кеш сбрасывается,
        следующий вызов пересоздаст модель с новым ключом."""
        self._model_initialized = False
        self._streaming_model_initialized = False
        self._chat_model = None
        self._chat_model_streaming = None
```

**Что хорошо.**

1. **Ленивая инициализация + кеш + явная инвалидация** — правильная схема «настройки
   из БД, клиент в памяти». Ключ обновляется через админку → `refresh_api_keys()` →
   пересоздание при следующем использовании. Никакой мутации живого клиента.
2. `callbacks` для трекинга токенов — идиоматичный способ LangChain вешать
   наблюдение (у Quorum это `TokenTrackingCallback` с записью в `TokenManager`).
3. Два отдельных кеша модели (стриминг/не-стриминг) — потому что коллбэки у
   `astream` и `ainvoke` должны быть разные. Тонко и правильно.

**Что плохо / риски.**

1. **`ChatOpenAI` против OpenRouter.** Официальная документация `langchain-openai`
   теперь прямо говорит: `ChatOpenAI` нацелен на официальный OpenAI API; нестандартные
   поля сторонних провайдеров (`reasoning_content`, `reasoning_details`) **не
   извлекаются и не сохраняются**; для OpenRouter/vLLM/DeepSeek рекомендованы
   профильные пакети (`ChatOpenRouter`, `ChatDeepSeek`). Код Quorum работает (OpenRouter
   совместим на уровне Chat Completions), но ответные поля, которых нет в спеке OpenAI,
   молча теряются.
2. `base_url="https://openrouter.ai/api/v1"` — строка-константа внутри метода; ключ из
   БД, а адрес провайдера нет.
3. `max_tokens=...` — у новых reasoning-моделей OpenAI параметр называется
   `max_completion_tokens`; при появлении их в `MODEL_MAP` понадобится ветвление (как
   сделано в RAG-проекте, §2.7).

**Правильный вариант с учётом документации LangChain:**

```python
# Вариант A: остаёмся на ChatOpenAI (если нужны только стандартные поля)
chat_model = ChatOpenAI(
    model=model_name,
    api_key=openrouter_key,
    base_url="https://openrouter.ai/api/v1",
    use_responses_api=False,   # ЯВНО: выбор API не должен выводиться из имени модели
    stream_usage=True,         # usage-метаданные при стриминге (нужно трекингу токенов)
    callbacks=callbacks,
)

# Вариант B: профильный пакет, когда нужны специфичные поля провайдера
# pip install langchain-openrouter
from langchain_openrouter import ChatOpenRouter
chat_model = ChatOpenRouter(
    model=model_name,
    api_key=openrouter_key,
    callbacks=callbacks,
)
```

> Пояснение по `use_responses_api`. Документация предупреждает: выбор между Chat
> Completions (`/v1/chat/completions`) и Responses (`/v1/responses`) **выводится в том
> числе из имени модели**, независимо от `base_url`. Для сторонних провайдеров это надо
> фиксировать явно, иначе очередное переименование модели может молча переключить API.

> Пояснение по `stream_usage`. Chat Completions по умолчанию не стримит статистику
> токенов; без этого флага трекинг стоимости на стриминговых ответах Quorum занижает
> расход.

---

### 2.7. Шлюз с fallback, кэшем и метриками (rag-knowledge-base-chatbot)

Самая зрелая интеграция в репозитории. `app/services/llm_gateway.py`:

```python
# rag-knowledge-base-chatbot/app/services/llm_gateway.py — как в репозитории (сокращено)

class LLMGateway(ABC):                       # абстракция: приложение зависит от интерфейса
    @abstractmethod
    async def chat(self, messages, temperature=0.1, **kwargs) -> LLMResponse: ...

class OpenAIGateway(LLMGateway):
    def __init__(self) -> None:
        # Конфигурация каскадом: env → БД (app_config) → Admin API
        api_key = get_llm_api_key()
        base_url = get_llm_base_url()        # "" = официальный OpenAI
        kwargs = {"api_key": api_key, "timeout": self._settings.llm_timeout_seconds}
        if base_url and base_url.strip():
            kwargs["base_url"] = base_url.strip()
        self._client = AsyncOpenAI(**kwargs)

    async def chat(self, messages, temperature=0.1, **kwargs) -> LLMResponse:
        model = kwargs.pop("model", None) or get_llm_model()
        models_to_try = [model, get_llm_fallback_model()]     # ← цепочка fallback

        # 1. Кэш ответов (Redis, ключ = sha256(messages+model+temperature))
        request_cache_key = _cache_key(messages, model, temperature)
        if cached := await self._get_cached(request_cache_key):
            return cached

        # 2. Промпт-кеширование на стороне OpenAI
        extra_params["prompt_cache_key"] = prompt_cache_key
        if self._settings.llm_prompt_cache_retention in ("24h", "in_memory"):
            extra_params["prompt_cache_retention"] = ...

        # 3. Разные имена лимита токенов для разных поколений моделей
        def _token_param(m: str) -> dict:
            if m.startswith("o1") or m.startswith("gpt-5"):
                return {"max_completion_tokens": max_tokens}
            return {"max_tokens": max_tokens}

        # 4. Попытки по цепочке моделей
        for m in models_to_try:
            try:
                response = await self._client.chat.completions.create(
                    model=m, messages=messages, temperature=temperature,
                    **_token_param(m), **extra_params,
                )
                ...
                await self._set_cached(request_cache_key, result)   # кэш
                llm_requests_total.labels(model=response.model, status="success").inc()  # метрики
                llm_tokens_total.labels(...).inc(inp)              # токены
                llm_cost_usd.labels(model=response.model).inc(estimate_cost(...))  # стоимость
                return result
            except Exception as e:
                last_error = e
                logger.warning("llm_model_failed", model=m, error=str(e))
                if m == models_to_try[-1]:
                    raise            # последняя модель в цепочке упала — роняем
```

**Что хорошо — это чек-лист «что должно быть в продакшен-интеграции»:**

1. **Абстракция `LLMGateway` + фабрика `get_llm_gateway()`** — приложение зависит от
   интерфейса, а не от SDK. Смена провайдера = новая реализация класса.
2. **Каскад конфигурации** env → БД → админ-API: модель и ключ меняются без redeploy
   (`llm_config.py` кеширует значения с TTL 60 c и обновляет при записи админом).
3. **Fallback-модель**: основной сценарий `gpt-5.2`, резерв `gpt-3.5-turbo`.
4. **`max_tokens` vs `max_completion_tokens`** по префиксу модели — единственное место
   в репозитории, где учтено, что reasoning-модели OpenAI не принимают старый параметр.
5. **`prompt_cache_key` / `prompt_cache_retention`** — использование серверного
   промпт-кеширования OpenAI (дешевле на повторяющихся префиксах — системные промпты
   ролей RAG-пайплайна как раз такие).
6. **Метрики и стоимость**: Prometheus-счётчики запросов/токенов/оценки стоимости +
   contextvars для трейсинга — каждый LLM-вызов виден в мониторинге.
7. **Redis-кэш идемпотентных запросов** с ключом от `messages+model+temperature`.

**Что можно улучшить.**

1. `except Exception` в цикле моделей не различает классы ошибок: если в запросе
   невалидный параметр (400), fallback-модель будет вызвана и упадёт с тем же — время
   потеряно, а причина замаскирована. Правильно: 4xx (кроме 408/429) — сразу raise,
   ретраить/fallback только 5xx/сеть/429 (подробнее §6).
2. Клиент Redis создаётся на каждый `_get_cached`/`_set_cached`
   (`redis.from_url(...)` внутри метода) — тот же антипаттерн «клиент на вызов», что и
   у httpx в §2.3, плюс `pickle.loads` из Redis — вектор атаки, если в Redis сможет
   писать кто-то ещё.
3. Fallback происходит внутри одного провайдера (другая модель). Отказ *провайдера*
   целиком (региональный сбой OpenAI) этим не покрывается — для этого нужен второй
   провайдер или шлюз (§8).

---

### 2.8. Эталон репозитория: контракт + фабрика + две реализации (examples/openrouter_chat_example)

Пример из свежего коммита — это выжимка правильных практик. `chat.py`:

```python
# examples/openrouter_chat_example/chat.py — как в репозитории (сокращено)

class ChatMessage(BaseModel):          # pydantic, а не dict: роль проверяется до запроса
    role: Role = Field(description='"system", "user" или "assistant"')
    content: str

@dataclass(slots=True)
class Usage:
    prompt_tokens: int = 0
    completion_tokens: int = 0

class ChatClient(ABC):
    async def chat(self, messages, *, model, temperature, max_tokens) -> ChatResult: ...
    async def stream(self, messages, *, model, ...) -> AsyncIterator[str]: ...
    async def aclose(self) -> None: ...       # клиент один на процесс — и он закрываем

class ProviderError(RuntimeError):
    """Отказ провайдера, который не удалось пережить fallback-моделями."""
    def __init__(self, message, *, status_code: int | None = None,
                 model: str | None = None, retryable: bool = False):
        ...
        self.retryable = retryable            # ← флаг «имеет ли смысл пробовать другую модель»

def create_client(backend: str, *, api_key: str, base_url: str, **kwargs) -> ChatClient:
    """Фабрика: точка расширения. Новый провайдер = новая ветка,
    остальное приложение не меняется. Импорты ленивые — проект не тянет
    обе библиотеки сразу."""
    if backend == "httpx":
        from .httpx_client import HttpxChatClient
        return HttpxChatClient(api_key=api_key, base_url=base_url, **kwargs)
    if backend == "openai":
        from .openai_client import OpenAISDKChatClient
        return OpenAISDKChatClient(api_key=api_key, base_url=base_url, **kwargs)
    raise ValueError(f"Неизвестная реализация клиента: {backend!r}")
```

Реализация на SDK (`openai_client.py`):

```python
class OpenAISDKChatClient(ChatClient):
    def __init__(self, *, api_key, base_url, app_url="http://localhost",
                 app_title="Chat Example", timeout_seconds=60.0):
        self._client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url.rstrip("/"),
            default_headers={                 # атрибуция агрегатора — один раз на клиент
                "HTTP-Referer": app_url,      # как OpenRouter идентифицирует приложение
                "X-Title": app_title,
            },
            timeout=timeout_seconds,
        )

    async def chat(self, messages, *, model, temperature=0.7, max_tokens=1024):
        response = await self._client.chat.completions.create(
            model=model,
            messages=[m.as_dict() for m in messages],
            temperature=temperature,
            max_completion_tokens=max_tokens,   # новый параметр — совместим с gpt-5/o-серией
        )
        if not response.choices:
            raise RuntimeError(f"Ответ без choices, модель {model}")
        ...
```

И реализация на httpx с классификацией HTTP-кодов:

```python
# httpx_client.py — как в репозитории
RETRYABLE_STATUS_CODES = frozenset({408, 409, 425, 429, 500, 502, 503, 504})

@staticmethod
def _raise_for_status(response: httpx.Response) -> None:
    if response.status_code < 400:
        return
    raise ProviderError(
        f"Агрегатор вернул {response.status_code}: {response.text[:500]}",
        status_code=response.status_code,
        retryable=response.status_code in RETRYABLE_STATUS_CODES,   # 400/401 → False
    )
```

**Почему это эталон.**

1. Приложение знает только контракт `ChatClient` — замена httpx ↔ SDK это одна строка
   в фабрике (`CHAT_BACKEND=openai` в `.env`).
2. `ProviderError.retryable` — **классификация ошибки уже встроена в контракт**:
   вызывающий код решает «попробовать другую модель или упасть», не разбирая HTTP-коды.
3. Заголовки атрибуции агрегатора задаются один раз в `default_headers`, а не в каждом
   запросе.
4. `config.py` — типизированные настройки с fallback-цепочкой моделей
   (`OPENROUTER_FALLBACK_MODELS="a, b"` → `settings.fallback_chain`).
5. Клиент создаётся один на процесс и явно закрывается (`aclose`).

---

## 3. Анатомия правильного клиента на AsyncOpenAI

Сводка по официальной документации OpenAI Python SDK.

### 3.1. Конструктор: что задавать всегда

```python
import httpx
from openai import AsyncOpenAI, DefaultAsyncHttpxClient

client = AsyncOpenAI(
    api_key="...",                       # или env OPENAI_API_KEY — тогда можно опустить

    # Провайдер/шлюз: любой OpenAI-совместимый endpoint.
    # Эквивалент env-переменной OPENAI_BASE_URL — SDK читает её сам.
    base_url="https://openrouter.ai/api/v1",

    # Таймауты. Дефолт SDK: 600 c на запрос, 5 c на connect — для web это много.
    # httpx.Timeout даёт гранулярность: total / connect / read / write / pool.
    timeout=httpx.Timeout(
        60.0,        # total: весь запрос, включая генерацию ответа
        connect=5.0, # не подключились за 5 c — сеть/провайдер лежит, ретрай/фолбэк
        read=30.0,   # пауза между чанками стрима (не путать с total!)
    ),

    # Ретраи SDK. Дефолт 2. Ретраятся: connection errors, 408, 409, 429, 5xx.
    # НЕ ретраятся: 400, 401, 403, 404, 422 — и это правильно, повторение
    # невалидного запроса бессмысленно. Backoff экспоненциальный с джиттером.
    max_retries=2,

    # Заголовки по умолчанию — атрибуция у агрегаторов (OpenRouter):
    # HTTP-Referer (URL приложения) и X-Title (название) идут в статистику рейтинга.
    default_headers={
        "HTTP-Referer": "https://myapp.example.com",
        "X-Title": "My App",
    },

    # Кастомный HTTP-клиент — когда нужны лимиты пула под свою нагрузку:
    http_client=DefaultAsyncHttpxClient(
        limits=httpx.Limits(max_keepalive_connections=20, max_connections=100),
    ),
)
```

> Пояснение. Разница `total` и `read` критична для стриминга: LLM может «думать»
> секунды, но чанки обязаны приходить регулярно. `read=30.0` отсечёт зависший стрим,
> не убивая долгую генерацию.

### 3.2. Жизненный цикл

```python
# Вариант 1 (скрипт): контекстный менеджер — закроет сам
async with AsyncOpenAI() as client:
    response = await client.chat.completions.create(...)

# Вариант 2 (приложение): клиент живёт с приложением, закрываем в lifespan
@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.llm = AsyncOpenAI(...)
    yield
    await app.state.llm.close()      # GC закроет и сам, но явно — предсказуемее
```

Три уровня переопределения настроек без пересоздания пула:

```python
# 1. per-request: with_options — разделяет httpx-пул с исходным клиентом
await client.with_options(timeout=30.0, max_retries=0).chat.completions.create(...)

# 2. per-request: разовые заголовки/тело
await client.chat.completions.create(
    ...,
    extra_headers={"X-Request-ID": request_id},
    extra_body={"models": ["openai/gpt-4o", "anthropic/claude-sonnet-4.5"]},  # OpenRouter fallback
)

# 3. новый клиент с общими настройками: copy()
fast_client = client.copy(timeout=10.0)
```

### 3.3. Ключи: три способа ротации

```python
# 1. Статический ключ (env) — дефолт, читается из OPENAI_API_KEY
client = AsyncOpenAI()

# 2. Ключ-коллбэк — SDK вызывает его на каждый запрос, можно менять значение в рантайме
client = AsyncOpenAI(api_key=lambda: key_provider.current_key())

# 3. Пересоздание клиента с инвалидацией кеша — паттерн Quorum (§2.6):
#    ключ обновлён в БД → флаги _model_initialized = False → новая модель на след. вызове
```

---

## 4. Подключение к конкретным провайдерам

### 4.1. OpenRouter (агрегатор, один ключ на сотни моделей)

```python
from openai import AsyncOpenAI

client = AsyncOpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY,          # именно OPENROUTER_API_KEY, не OPENAI_API_KEY
    default_headers={
        "HTTP-Referer": "https://myapp.example.com",   # опционально: атрибуция в рейтинге
        "X-Title": "My App",
    },
)

response = await client.chat.completions.create(
    model="openai/gpt-4o",               # формат агрегатора: provider/model-name
    messages=[{"role": "user", "content": "Hi"}],
    # extra_body — канал для аргументов, которых нет в спеке OpenAI:
    extra_body={
        "models": [                       # fallback-список НА СТОРОНЕ OpenRouter:
            "openai/gpt-4o",              # если основной провайдер лёг, агрегатор сам
            "anthropic/claude-sonnet-4.5" # переключит на следующий из списка
        ],
        # "provider": {"require_parameters": True},  # только провайдеры с полной поддержкой параметров
    },
)
```

> Пояснение. `extra_body` — официальный механизм SDK для нестандартных полей провайдера:
> содержимое добавляется в JSON тела запроса как есть. Fallback внутри агрегатора не
   заменяет ваш собственный fallback между *агрегаторами*, но бесплатно покрывает отказ
   одного апстрим-провайдера.

### 4.2. GitHub Models (как в AI-Chatbot)

```python
client = AsyncOpenAI(
    api_key=settings.GITHUB_TOKEN,                          # PAT GitHub
    base_url="https://models.github.ai/inference/",         # OpenAI-совместимый вход
)
response = await client.chat.completions.create(
    model="openai/gpt-4o",           # тоже формат provider/model
    messages=[...],
)
```

### 4.3. Azure OpenAI (v1 API — через тот же ChatOpenAI/AsyncOpenAI)

```python
# Прямой ключ:
client = AsyncOpenAI(
    base_url="https://{your-resource}.openai.azure.com/openai/v1/",
    api_key="your-azure-api-key",
)

# Entra ID (Azure AD): ключ = функция, возвращающая свежий bearer-токен
from azure.identity import DefaultAzureCredential, get_bearer_token_provider

token_provider = get_bearer_token_provider(
    DefaultAzureCredential(), "https://cognitiveservices.azure.com/.default"
)
client = AsyncOpenAI(
    base_url="https://{your-resource}.openai.azure.com/openai/v1/",
    api_key=token_provider,          # callable — SDK сам обновляет токен
)
```

### 4.4. Groq, vLLM, Ollama, LiteLLM Proxy

Все — OpenAI-совместимые, различаются только `base_url` и именем модели:

```python
Groq:          base_url="https://api.groq.com/openai/v1"      # или нативный AsyncGroq
vLLM (self):   base_url="http://localhost:8000/v1", api_key="EMPTY"
Ollama:        base_url="http://localhost:11434/v1"
LiteLLM Proxy: base_url="http://litellm:4000"                  # ключ — виртуальный ключ LiteLLM
```

> Пояснение. Это и есть причина, почему «подменить `base_url`» считается каноническим
> паттерном: один и тот же код приложения работает с любым из этих endpoint'ов, а
> выбор провайдера становится конфигурацией (env), а не кодом.

---

## 5. LangChain ChatOpenAI: когда и как правильно

### 5.1. Что говорит документация

- `ChatOpenAI` **нацелен только на официальный OpenAI API**. Нестандартные поля
  сторонних провайдеров (`reasoning_content` у DeepSeek, `reasoning_details` у
  OpenRouter-моделей) не извлекаются и не сохраняются.
- Для провайдеров, расширяющих Chat Completions/Responses формат (OpenRouter, LiteLLM,
  vLLM, DeepSeek) рекомендованы профильные пакеты: `ChatOpenRouter`, `ChatDeepSeek`,
  `ChatGroq` и т.д. — их список в доке «Chat models → Chat Completions API compatible».
- Если всё же используете `ChatOpenAI` с чужим `base_url` — фиксируйте
  `use_responses_api` явно: автоматический выбор API выводится в том числе из имени
  модели, независимо от `base_url`.

### 5.2. Шпаргалка параметров

```python
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(
    model="openai/gpt-4o",
    api_key=OPENROUTER_API_KEY,
    base_url="https://openrouter.ai/api/v1",

    use_responses_api=False,  # ЯВНО фиксируем Chat Completions для стороннего провайдера
    stream_usage=True,        # usage в стриминговых чанках (без этого трекинг токенов
                              # на стриминге не работает)
    timeout=60,               # таймаут запроса
    max_retries=2,            # пробрасывается в AsyncOpenAI внутри

    # model_kwargs vs extra_body — часто путают:
    model_kwargs={            # СТАНДАРТНЫЕ параметры спеки OpenAI, не имеющие
        "max_completion_tokens": 1024,   # собственного поля у ChatOpenAI
        "stream_options": {"include_usage": True},
    },
    extra_body={              # НЕСТАНДАРТНЫЕ свойства провайдера, добавляются в JSON как есть
        "models": ["openai/gpt-4o", "anthropic/claude-sonnet-4.5"],  # OpenRouter fallback
    },
)
```

### 5.3. Вызовы: ainvoke / astream и конвертация сообщений

```python
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

# Конвертация OpenAI-формата → LangChain (паттерн из Quorum base_agent.py)
def to_langchain(messages: list[dict]) -> list:
    out = []
    for m in messages:
        role, content = m.get("role", "user"), m.get("content", "")
        if role == "system":
            out.append(SystemMessage(content=content))
        elif role == "assistant":
            out.append(AIMessage(content=content))
        else:
            out.append(HumanMessage(content=content))
    return out

# Полный ответ
response = await llm.ainvoke(to_langchain(messages))
print(response.content, response.response_metadata.get("model_name"))

# Стриминг
async for chunk in llm.astream(to_langchain(messages)):
    if chunk.content:
        print(chunk.content, end="")
# usage при stream_usage=True доступен в response_metadata последнего чанка:
# chunk.response_metadata["token_usage"]
```

### 5.4. Наблюдение: callbacks (паттерн Quorum)

```python
from langchain_core.callbacks import AsyncCallbackHandler

class TokenTrackingCallback(AsyncCallbackHandler):
    async def on_llm_end(self, response, *, run_id, parent_run_id, **kwargs):
        # response.llm_output["token_usage"] — {prompt_tokens, completion_tokens, total}
        usage = response.llm_output.get("token_usage", {})
        await self._on_usage(usage)

llm = ChatOpenAI(..., callbacks=[TokenTrackingCallback(...)])
```

> Пояснение. Это позволяет считать токены/стоимость, не трогая код вызовов: коллбэк
> навешивается на модель. Именно так Quorum ведёт in-memory трекинг по сессиям.

---

## 6. Устойчивость: ошибки, ретраи, fallback, circuit breaker

### 6.1. Классификация ошибок — до любой стратегии ретраев

| Класс | Примеры | Что делать | Ретраить? | Fallback-модель? | Circuit breaker? |
|---|---|---|---|---|---|
| Ошибка запроса | 400, 401, 403, 404, 422, invalid JSON | чинить запрос/ключ, не повторять | нет | нет | нет |
| Свои лимиты | 429 rate limit | уважать `Retry-After`, снизить RPS, ставить в очередь | да, по заголовку | можно | нет (это не про здоровье провайдера) |
| Системный сбой провайдера | 500, 502, 503, 504, 529 overloaded | backoff с джиттером | да | да | **да — только этот класс** |
| Сеть/таймаут | connect timeout, DNS, APIConnectionError | backoff | да | да | по политике (обычно да) |
| Некорректный ответ | пустой choices, не тот schema | fail loudly, алертить качество | нет | можно один раз | нет |

> Пояснение. Главная ошибка из статей о production-надёжности: «один `@retry` на все
> исключения». Breaker, открытый из-за того, что вы сами слал­и невалидные запросы или
> выжгли свою квоту, — это самодиверсия: сервис отключает себя за проблемы, не имеющие
> отношения к здоровью провайдера. Три класса и один экономический флаг (429 = свои
> лимиты) покрывают почти все случаи.

### 6.2. Уровень 1: ретраи SDK (уже включены)

SDK ретраит connection errors, 408, 409, 429, 5xx с экспоненциальным backoff и
джиттером (дефолт `max_retries=2`, старт задержки ~0.5 c, потолок ~8 c). Известный
issue openai-python (#1059): переиспользуемый клиент **без** ретраев ловит
`APIConnectionError` на очередях конкурентных запросов; те же запросы с
`max_retries=2` — проходят. Вывод: пул соединений + включённые ретраи — это одна
фича, а не две.

```python
# SDK-ретраев обычно достаточно. Не дублируйте их своим @retry вокруг каждого вызова —
# иначе 2 SDK-ретрая × 3 ваших = 6 попыток и шторм на 429.
client = AsyncOpenAI(max_retries=2, timeout=httpx.Timeout(60.0, connect=5.0))
```

### 6.3. Уровень 1½: свой ретраи-слой, когда SDK не видит ошибку

SDK ретраит HTTP-ошибки, но не «провайдер ответил 200 с мусором». Для этого — tenacity
с **whitelist исключений**:

```python
from tenacity import retry, stop_after_attempt, wait_exponential_jitter, retry_if_exception_type
from openai import APIConnectionError, InternalServerError, RateLimitError

class EmptyLLMResponse(RuntimeError):
    """200 OK, но choices пустые или контент None."""

@retry(
    retry=retry_if_exception_type((APIConnectionError, InternalServerError,
                                   RateLimitError, EmptyLLMResponse)),
    stop=stop_after_attempt(3),
    wait=wait_exponential_jitter(initial=0.5, max=8),
    reraise=True,
)
async def call_llm(client, **params) -> str:
    response = await client.chat.completions.create(**params)
    if not response.choices or not response.choices[0].message.content:
        raise EmptyLLMResponse(f"пустой ответ от {params.get('model')}")
    return response.choices[0].message.content
```

> Пояснение. `reraise=True` пробрасывает последнее исключение как есть, а не заворачивает
> в `RetryError` — логи остаются читаемыми. Whitelist — обязательная часть: без него
> tenacity будет ретраить и `AuthenticationError`, и опечатки в параметрах.

### 6.4. Уровень 2: fallback-модели (паттерн RAG-проекта)

```python
async def chat_with_fallback(client, messages: list[dict]) -> LLMResponse:
    models = [PRIMARY_MODEL, FALLBACK_MODEL]        # напр. gpt-5.2 → gpt-4o-mini
    last_error: Exception | None = None

    for model in models:
        try:
            response = await client.chat.completions.create(
                model=model, messages=messages,
                **token_param_for(model),            # max_tokens vs max_completion_tokens
            )
            if not response.choices:
                raise EmptyLLMResponse(model)
            return to_llm_response(response)

        except (AuthenticationError, BadRequestError, NotFoundError) as e:
            # Ошибка запроса: другая модель НЕ поможет — роняем сразу.
            raise ProviderError(str(e), status_code=e.status_code, retryable=False) from e
        except (RateLimitError, APIConnectionError, InternalServerError) as e:
            last_error = e                          # временная — пробуем следующую модель
            logger.warning("model_failed_try_next", model=model, error=str(e))

    raise ProviderError("Все модели недоступны", retryable=True) from last_error
```

> Пояснение. Отличие от RAG-версии: здесь 4xx-ошибки запроса роняют цикл сразу, не
> тратя время на заведомо бессмысленный вызов fallback-модели. Для экономии на
> reasoning-моделях fallback часто делают «вниз» — та же задача более дешёвой моделью
> вместо падения.

### 6.5. Уровень 3: circuit breaker — только на системные сбои

```python
# Упрощённый breaker на ошибках одного провайдера (порог: 5 системных сбоев за 60 c)
import time

class ProviderCircuitBreaker:
    def __init__(self, failure_threshold: int = 5, window: float = 60.0,
                 cooldown: float = 30.0):
        self.failures: list[float] = []      # таймстампы СИСТЕМНЫХ ошибок
        self.opened_at: float | None = None
        self.failure_threshold = failure_threshold
        self.window = window
        self.cooldown = cooldown

    def allow_request(self) -> bool:
        if self.opened_at is None:
            return True
        if time.monotonic() - self.opened_at >= self.cooldown:
            self.opened_at = None            # half-open: пропускаем пробный запрос
            self.failures.clear()
            return True
        return False                         # open: фейлимся мгновенно, не дёргая провайдера

    def record_failure(self, systemic: bool) -> None:
        if not systemic:
            return                           # 400/429 НЕ трипают breaker
        now = time.monotonic()
        self.failures = [t for t in self.failures if now - t <= self.window]
        self.failures.append(now)
        if len(self.failures) >= self.failure_threshold:
            self.opened_at = now

    def record_success(self) -> None:
        self.failures.clear()
        self.opened_at = None
```

> Пояснение. Смысл breaker — не «надёжнее ретраить», а **прекратить ретраи** на
> лежащем провайдере: при 100 RPM и пятиминутном отказе без breaker вы шлёте сотни
> запросов в стену (каждый с таймаутом и ретраями), с breaker — падаете мгновенно и
> переключаетесь на fallback-провайдера. Триггер — только системные сбои (5xx/сеть);
> ваш собственный 429 не должен отключать вам провайдера.

### 6.6. Слоистая картина целиком

```text
запрос → очередь с лимитами RPM/TPM (свои квоты, 429 не должен случаться вообще)
       → circuit breaker (открыт? → мгновенно на fallback-провайдера)
       → вызов primary с SDK-ретраями (backoff+джиттер, только 408/409/429/5xx/сеть)
       → не помогло → fallback-модель (дешевле/резервнее)
       → не помогло → fallback-провайдер (другой агрегатор / self-hosted)
       → не помогло → честная ошибка пользователю + алерт
```

Каждый слой отвечает на свой вопрос: очередь — «мы не душим провайдера сами»,
breaker — «мы не штормим лежащего», ретраи — «пережили моргание», fallback —
«пользователь получил ответ, пока чиним основное».

---

## 7. Смена конфигурации в рантайме без рестарта

Сводка трёх рабочих схем (все три уже есть в репозитории или SDK):

```python
# Схема A (Quorum): ленивое создание + кеш + инвалидация
#   ключ обновлён в БД → refresh_api_keys() → модель пересоздастся на следующем вызове.
#   Плюс: просто, работает с любым SDK. Минус: активные long-lived объекты нужно
#   инвалидировать вручную (Quorum хранит _chat_model у каждого агента).

# Схема B (quickstart сегодня): клиент на каждый запрос
#   Плюс: настройки из env подхватываются мгновенно. Минус: пул не переиспользуется,
#   см. §2.4. Правильная замена — схема A на уровне приложения.

# Схема C (SDK): api_key-коллбэк и with_options
client = AsyncOpenAI(api_key=lambda: current_key_from_db())   # ключ читается на каждый запрос
regional = client.with_options(base_url="https://eu.api.openai.com/v1")  # база на подмножество
```

Чего не делать: **мутировать поля живого клиента** (`client.base_url = ...`,
`client.api_key = ...`). Под конкурентными запросами это гонка (реальный пример в
репозитории — §2.5). Клиент иммутабелен: меняем настройки — создаём новый объект
(через `copy()` или фабрику) и атомарно подменяем ссылку.

Для LangChain есть четвёртая схема — объект `ChatOpenAI` дешёвый, его можно
пересоздавать per-call из актуальных настроек, если вызовы редкие; при частых —
кешировать и инвалидировать по флагу (как Quorum).

---

## 8. Один провайдер напрямую, агрегатор или свой шлюз?

| Критерий | Напрямую (OpenAI/Groq/…) | Агрегатор (OpenRouter) | Свой шлюз (LiteLLM Proxy) |
|---|---|---|---|
| Время запуска | минута | минута | часы (deploy, БД, обновления) |
| Количество ключей | по ключу на провайдера | один ключ | один виртуальный ключ на команду |
| Fallback между провайдерами | пишем сами | из коробки (`extra_body.models`) | из коробки (router config) |
| Где проходят промпты | провайдер | провайдер через третью сторону | ваша инфраструктура |
| Лимиты/бюджеты по командам | нет | частично | да (virtual keys, budgets) |
| Стоимость | цена провайдера | цена + комиссия | цена провайдера + ваш хостинг |
| Задержка | минимальная | + прыжок через агрегатор | ~+4 мс, ~2–3% throughput (замеры сообщества) |

Практическое правило:

- **Один проект, один-два провайдера** → `AsyncOpenAI`/`ChatOpenAI` с `base_url`
  (как RAG-проект или Quorum). Абстракция-контракт из `openrouter_chat_example`
  позволяет добавить второго провайдера позже.
- **Нужно много чужих моделей быстро, без ops** → OpenRouter (llm-council так и делает:
  4 провайдера одним ключом).
- **Несколько команд, общие бюджеты, комплаенс на промпты** → LiteLLM Proxy / Portkey /
  Kong AI Gateway; приложения при этом всё равно говорят на OpenAI-формате с
  `base_url` на шлюз — паттерн подключения не меняется.

Пример LiteLLM Router в коде (SDK-режим, без proxy):

```python
from litellm import Router

router = Router(
    model_list=[
        {"model_name": "primary",          # логическое имя для приложения
         "litellm_params": {"model": "openai/gpt-5.2", "api_key": "..."}},
        {"model_name": "primary",
         "litellm_params": {"model": "groq/llama-3.1-8b-instant", "api_key": "..."}},
    ],
    fallbacks=[{"primary": ["primary"]}],   # вторая запись того же имени = failover
    num_retries=2,
    timeout=60,
)
resp = await router.acompletion(model="primary", messages=[...])
```

> Пояснение. Router сам делает то, что описано в §6: ретраи, cooldowns, fallback между
> deployment'ами. Это альтернатива «писать свой шлюз-класс» — RAG-проект написал свой
  (`LLMGateway`), и для одного провайдера это оправдано: меньше магии, весь код виден.

---

## 9. Эталонный клиент: сводная реализация

Объединяет практики из `openrouter_chat_example` (контракт+фабрика),
RAG-проекта (fallback, метрики) и документации SDK (таймауты, ретраи). Это модель для
копирования в новый проект:

```python
"""LLM-клиент приложения: один на процесс, контракт + фабрика + устойчивость."""

from __future__ import annotations

import httpx
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass

from openai import AsyncOpenAI

RETRYABLE_STATUS_CODES = frozenset({408, 409, 425, 429, 500, 502, 503, 504})


class ProviderError(RuntimeError):
    def __init__(self, message: str, *, status_code: int | None = None,
                 model: str | None = None, retryable: bool = False):
        super().__init__(message)
        self.status_code, self.model, self.retryable = status_code, model, retryable


@dataclass(slots=True)
class ChatResult:
    content: str
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    finish_reason: str | None = None


class ChatClient(ABC):
    @abstractmethod
    async def chat(self, messages: list[dict], *, model: str,
                   temperature: float = 0.7, max_tokens: int = 1024) -> ChatResult: ...

    @abstractmethod
    def stream(self, messages: list[dict], *, model: str,
               temperature: float = 0.7, max_tokens: int = 1024) -> AsyncIterator[str]: ...

    @abstractmethod
    async def aclose(self) -> None: ...


class OpenAICompatibleClient(ChatClient):
    """Любой OpenAI-совместимый endpoint: OpenAI, OpenRouter, GitHub Models, vLLM…"""

    def __init__(self, *, api_key: str, base_url: str = "https://api.openai.com/v1",
                 timeout_seconds: float = 60.0, max_retries: int = 2,
                 default_headers: dict[str, str] | None = None,
                 fallback_models: tuple[str, ...] = ()) -> None:
        self._fallback_models = fallback_models
        self._client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url.rstrip("/"),
            timeout=httpx.Timeout(timeout_seconds, connect=5.0),
            max_retries=max_retries,               # ретраи SDK: 408/409/429/5xx/сеть
            default_headers=default_headers or {},
        )

    @staticmethod
    def _token_param(model: str, max_tokens: int) -> dict:
        # reasoning-модели (o*, gpt-5*) не принимают max_tokens
        if model.startswith(("o1", "o3", "o4", "gpt-5")):
            return {"max_completion_tokens": max_tokens}
        return {"max_tokens": max_tokens}

    async def chat(self, messages, *, model, temperature=0.7, max_tokens=1024) -> ChatResult:
        last_error: Exception | None = None
        for m in (model, *self._fallback_models):
            try:
                response = await self._client.chat.completions.create(
                    model=m, messages=messages, temperature=temperature,
                    **self._token_param(m, max_tokens),
                )
                if not response.choices:
                    raise ProviderError(f"Пустой ответ от {m}", model=m, retryable=True)
                choice, usage = response.choices[0], response.usage
                return ChatResult(
                    content=choice.message.content or "",
                    model=response.model or m,
                    prompt_tokens=getattr(usage, "prompt_tokens", 0) or 0,
                    completion_tokens=getattr(usage, "completion_tokens", 0) or 0,
                    finish_reason=choice.finish_reason,
                )
            except ProviderError:
                raise                                   # наша классификация уже точная
            except Exception as e:                      # openai-исключения: e.status_code
                status = getattr(e, "status_code", None)
                if status is not None and status not in RETRYABLE_STATUS_CODES:
                    # 400/401/404 — ошибка запроса, fallback бессмыслен
                    raise ProviderError(str(e), status_code=status, model=m,
                                        retryable=False) from e
                last_error = e                          # временная — следующая модель
        raise ProviderError(f"Все модели недоступны: {last_error}", model=model,
                            retryable=True) from last_error

    async def stream(self, messages, *, model, temperature=0.7, max_tokens=1024):
        stream = await self._client.chat.completions.create(
            model=model, messages=messages, temperature=temperature,
            **self._token_param(model, max_tokens), stream=True,
        )
        async for chunk in stream:
            for choice in chunk.choices or []:
                if choice.delta.content:
                    yield choice.delta.content

    async def aclose(self) -> None:
        await self._client.close()


# ---- wiring: один клиент на процесс, живёт с приложением -------------------

_client: ChatClient | None = None

def init_client(settings) -> None:
    """Вызывается один раз в lifespan приложения."""
    global _client
    _client = OpenAICompatibleClient(
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
        fallback_models=settings.llm_fallback_models,
        default_headers=settings.provider_attribution_headers,  # HTTP-Referer/X-Title
    )

def get_client() -> ChatClient:
    """DI для роутеров: Depends(get_client)."""
    assert _client is not None, "init_client не вызван (lifespan)"
    return _client

async def close_client() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None
```

Подключение в FastAPI:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    init_client(settings)         # пул соединений открывается один раз
    yield
    await close_client()

app = FastAPI(lifespan=lifespan)

@router.post("/chat")
async def chat(body: ChatRequest, client: ChatClient = Depends(get_client)):
    try:
        result = await client.chat(body.messages, model=settings.llm_model)
    except ProviderError as e:
        if e.retryable:
            raise HTTPException(503, "Провайдер временно недоступен")
        raise HTTPException(502, f"Ошибка запроса к провайдеру: {e}")
    return {"content": result.content, "model": result.model}
```

---

## 10. Конкретные рекомендации по проектам репозитория

| Проект | Проблема | Рекомендация | Раздел |
|---|---|---|---|
| AI-Chatbot | `base_url`/модель в коде; нет таймаутов; пустой ответ = `""` | вынести в `Settings`; `timeout=30`; пустой ответ — исключение | §2.1 |
| GroqStreamChain | синхронный стрим блокирует event loop; мёртвый `ChatGroq`; мутация списка system prompt | `AsyncGroq` + `async for`; удалить `ChatGroq`; собирать новый список | §2.2 |
| llm-council-karpathy | `httpx.AsyncClient` на каждый запрос; `print` вместо логов | один клиент на процесс (модуль/класс); logger | §2.3 |
| quickstart | `Depends(lambda: AsyncOpenAI())` — клиент на запрос; мутация `client.base_url` (гонка) | lifespan-клиент + `with_options`; `copy(base_url=...)` для контейнеров | §2.4, §2.5 |
| Quorum | `ChatOpenAI` против OpenRouter без `use_responses_api`; `base_url` в коде; `max_tokens` для новых моделей | `use_responses_api=False`, `stream_usage=True`; `base_url` в настройки; `_token_param`-ветвление; рассмотреть `ChatOpenRouter` | §2.6, §5 |
| RAG chatbot | `except Exception` не различает классы; Redis-клиент на вызов; `pickle` из кэша | 4xx — сразу raise; постоянный Redis-соединение; подписанный/версионированный формат кэша | §2.7, §6.4 |

Общий знаменатель: везде, где сегодня клиент создаётся на запрос или на вызов —
перевести на «один клиент на процесс» (lifespan/синглтон) с явным `close()`; везде, где
`except Exception` — ввести классификацию по `status_code` с признаком retryable; и
держать конфигурацию провайдера (`base_url`, модель, fallback-цепочка) в настройках,
а не в коде.
