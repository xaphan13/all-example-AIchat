# Работа с агрегаторами AI-провайдеров в 6 проектах (Часть 1: инвентаризация кода)

> Дата: 21.09.2026
> Источник: фактический код проектов (пути и номера строк сверены с рабочим деревом)
> Часть 1 из 3. Часть 2 — обзор библиотек доступа, Часть 3 — надёжность и практика.

## 0. О чём этот цикл

Задача цикла — описать **способы доступа к агрегаторам моделей** (OpenRouter и аналогам):
через какие библиотеки, с какими параметрами, какие есть практики надёжности.

Терминология, которой я держусь:

- **Агрегатор (роутер)** — сервис, дающий один API и один ключ к моделям многих вендоров.
  Примеры: OpenRouter, Portkey, LiteLLM Proxy, YesScale, Together, Novita AI.
- **Прямой провайдер** — сам вендор: OpenAI, Anthropic, Google, Groq, GitHub Models.
- **OpenAI-совместимый endpoint** — сервер, понимающий формат Chat Completions
  (`POST /v1/chat/completions`). Именно это свойство делает агрегатор подключаемым
  «заменой `base_url`».

Главный факт по репозиторию: **из 6 проектов через агрегатор ходят только 2**
(`llm-council-karpathy` и `Quorum`, оба — OpenRouter), и оба — **разными способами**,
причём **ни один** не использует официальный SDK. Остальные 4 проекта работают
с прямыми провайдерами.

---

## 1. Сводная таблица: как каждый проект выходит в сеть к модели

| Проект | Провайдер / агрегатор | Библиотека | base_url задаётся? | Ключ | Стриминг |
|---|---|---|---|---|---|
| AI-Chatbot | GitHub Models | `openai.AsyncOpenAI` | да, литерал в коде | `GITHUB_TOKEN` (pydantic-settings) | нет |
| GroqStreamChain | Groq (прямой) | `groq.Groq` (+ мёртвый `ChatGroq`) | нет (дефолт SDK) | `GROQ_API_KEY` (dotenv) | да, `stream=True` |
| llm-council-karpathy | **OpenRouter** | **`httpx.AsyncClient` вручную** | да, константа в `config.py` | `OPENROUTER_API_KEY` (dotenv) | нет |
| openai-responses-quickstart | OpenAI (прямой) | `openai.AsyncOpenAI` | нет (дефолт SDK) | `OPENAI_API_KEY` (env SDK) | да, Responses API |
| Quorum | **OpenRouter** | **`langchain_openai.ChatOpenAI`** | да, литерал в конструкторе | `OPENROUTER_API_KEY` (БД → env) | да, `astream` |
| rag-knowledge-base-chatbot | OpenAI / любой совместимый (в т.ч. YesScale) | `openai.AsyncOpenAI` внутри `LLMGateway` | да, из БД `app_config` / env | `llm_api_key` (БД → env) | нет (псевдостриминг) |

---

## 2. Способ А: ручной HTTP-запрос (`httpx`) — llm-council-karpathy

Самый «низкоуровневый» способ. Проект вообще не подключает SDK — он делает POST на
`/api/v1/chat/completions` руками. Единственное место, откуда уходит запрос к модели, —
`backend/openrouter.py`:

```python
# llm-council-karpathy/backend/openrouter.py:25-53
headers = {
    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
    "Content-Type": "application/json",
}

payload = {
    "model": model,
    "messages": messages,
}

try:
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(
            OPENROUTER_API_URL,
            headers=headers,
            json=payload
        )
        response.raise_for_status()

        data = response.json()
        message = data['choices'][0]['message']

        return {
            'content': message.get('content'),
            'reasoning_details': message.get('reasoning_details')
        }

except Exception as e:
    print(f"Error querying model {model}: {e}")
    return None
```

Endpoint и ключ — в `backend/config.py`:

```python
# llm-council-karpathy/backend/config.py:9, 23
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
```

**Наблюдения по этому способу:**

- **Плюс:** нулевые зависимости от версий SDK — ключ, URL и тело запроса полностью
  под контролем; легко добавить любые недокументированные поля агрегатора.
- **Минус — отсутствуют рекомендательные заголовки агрегатора.** OpenRouter в
  документации указывает заголовки `HTTP-Referer` и `X-OpenRouter-Title` (алиас
  `X-Title`) как необязательные, но полезные: они атрибутируют приложение в рейтингах
  и статистике. Здесь их нет — только `Authorization` и `Content-Type`
  (`openrouter.py:25-28`).
- **Минус — нет валидации ключа.** `os.getenv(...)` без проверки на `None`: при пустом
  ключе уйдёт `Authorization: Bearer None` и вернётся невнятная 401.
- **Минус — нет переиспользования соединения.** `httpx.AsyncClient` создаётся внутри
  функции на **каждый** вызов модели; при `asyncio.gather` по 4 моделям это 4 отдельных
  пула соединений. Правильнее держать один клиент на процесс.
- **Типизация ответа слабая:** `data['choices'][0]['message']` — словари без моделей,
  ошибка формата проявится в рантайме.

**Как тот же вызов выглядел бы «правильно» для httpx** (один клиент + рекомендованные
заголовки):

```python
import os
import httpx

_client = httpx.AsyncClient(
    base_url="https://openrouter.ai/api/v1",
    timeout=httpx.Timeout(120.0, connect=5.0),
    headers={
        "Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}",
        "HTTP-Referer": "http://localhost:5173",
        "X-OpenRouter-Title": "LLM Council",
    },
)

async def query_model(model: str, messages: list[dict]) -> dict:
    response = await _client.post(
        "/chat/completions",
        json={"model": model, "messages": messages},
    )
    response.raise_for_status()
    return response.json()["choices"][0]["message"]
```

---

## 3. Способ Б: LangChain `ChatOpenAI` поверх OpenRouter — Quorum

Quorum подключает агрегатор через привычный OpenAI-интерфейс, но обёрнутый во фреймворк
LangChain. Ядро — конструктор модели в базовом агенте
(`../Quorum/backend/src/agents/base_agent.py`):

```python
# Quorum/backend/src/agents/base_agent.py
from langchain_openai import ChatOpenAI

chat_model = ChatOpenAI(
    model=model_name,
    temperature=self.config.temperature,
    max_tokens=self.config.max_tokens,
    api_key=openrouter_key,
    base_url="https://openrouter.ai/api/v1",   # OpenRouter, OpenAI-совместимый вход
    callbacks=callbacks,                        # TokenTrackingCallback
)
```

Идентификаторы моделей — формат агрегатора `vendor/model`
(`../Quorum/backend/src/agents/agent_factory.py`):

```python
MODEL_MAP = {
    AgentType.CLAUDE_MAIN: "anthropic/claude-3.5-sonnet",
    AgentType.CLAUDE_SUB: "anthropic/claude-3-5-haiku",
    AgentType.GPT5: "openai/gpt-4o",
}
```

Ключ читается двухуровнево — сначала из БД настроек, потом из окружения
(`../Quorum/backend/src/core/settings_service.py`):

```python
async def get_openrouter_api_key(self) -> str:
    """Get OpenRouter API key from database or fallback to environment."""
    key = settings.get("openrouter_api_key", "")
    ...
    return env_settings.openrouter_api_key
```

**Наблюдения:**

- **Плюс:** код агента не знает, что за провайдер под капотом — он работает с
  `BaseChatModel`; тип агента → строка модели, дальше всё одинаково.
- **Плюс:** ключ можно поменять через настройки приложения (БД) без передеплоя, и он
  маскируется при выдаче наружу (`settings_repository.py`, `_mask_api_key`).
- **Плюс:** вся телеметрия LangChain доступна — `callbacks` позволяет слушать usage и
  считать стоимость (`TokenTrackingCallback`).
- **Минус — заголовки атрибуции тоже не передаются.** `ChatOpenAI` не имеет
  `HTTP-Referer` / `X-Title` в конструкторе из коробки, а код их не задаёт. Чтобы
  добавить, нужен `default_headers` (см. Часть 2, раздел про ChatOpenAI).
- **Минус — нет настроек надёжности:** ни `timeout`, ни `max_retries` не переданы, то
  есть действуют дефолты библиотеки, а не осознанный выбор.
- **Ловушка:** `ChatOpenAI` считает, что говорит с OpenAI, и может угадывать
  специфику вендора по имени модели. Для агрегатора это лотерея — корректнее
  явно фиксировать поведение через профиль/настройки.

---

## 4. Прямые провайдеры: где агрегатор не используется

### AI-Chatbot — GitHub Models через OpenAI SDK

```python
# AI-Chatbot/app/services/chat.py:5-8
client = AsyncOpenAI(
    api_key=settings.GITHUB_TOKEN,
    base_url="https://models.github.ai/inference/",
)
```

Обратите внимание: **тот же приём, что и для агрегатора** — SDK OpenAI + подменённый
`base_url`. GitHub Models отдаёт OpenAI-совместимый вход, поэтому код неотличим от
подключения OpenRouter; отличается только URL и имя модели `openai/gpt-4o`
(тоже в формате `vendor/model`). Технически это значит, что агрегатор подключается
в этот проект одной строкой.

### GroqStreamChain — нативный SDK вендора

```python
# GroqStreamChain/services/llm_service.py:15-21
self.client = Groq(api_key=GROQ_API_KEY)
self.langchain_client = ChatGroq(
    groq_api_key=GROQ_API_KEY,
    model_name=MODEL_NAME,
    temperature=LLM_CONFIG["temperature"],
    max_tokens=LLM_CONFIG["max_tokens"],
)
```

Интересный гибрид: в проекте одновременно нативный клиент Groq и LangChain-обёртка
`ChatGroq`, но фактически используется нативный, а `langchain_client` — мёртвый код.
С точки зрения темы отчёта: **нативный SDK вендора — тупик для агрегатора**, потому что
`groq.Groq` жёстко привязан к хосту Groq и не принимает `base_url`.

### openai-responses-python-quickstart — прямой OpenAI

```python
# openai-responses-python-quickstart/routers/chat.py:104
client: Annotated[AsyncOpenAI, Depends(lambda: AsyncOpenAI())]
```

Клиент создаётся без аргументов — SDK сам берёт `OPENAI_API_KEY` из окружения.
Проект использует **Responses API** (`client.responses.create`), а не Chat Completions.
Это важно для темы: **Responses API пока не является «общим языком» агрегаторов** —
OpenRouter и аналоги в первую очередь предоставляют Chat Completions, поэтому
подключение этого проекта к агрегатору потребует не замены URL, а переработки
разбора событий стрима.

### rag-knowledge-base-chatbot — собственная абстракция шлюза

Единственный проект с настоящей абстракцией над провайдером
(`app/services/llm_gateway.py`):

```python
class LLMGateway(ABC):
    """Abstract LLM gateway interface."""

    @abstractmethod
    async def chat(self, messages: list[dict[str, str]],
                   temperature: float = 0.1, **kwargs: Any) -> LLMResponse: ...


class OpenAIGateway(LLMGateway):
    """OpenAI Chat Completions with fallback, cache, retry, token budget."""

    def __init__(self) -> None:
        self._settings = get_settings()
        api_key = get_llm_api_key()
        base_url = get_llm_base_url()
        kwargs: dict = {"api_key": api_key,
                        "timeout": self._settings.llm_timeout_seconds}
        if base_url and base_url.strip():
            kwargs["base_url"] = base_url.strip()
        self._client = AsyncOpenAI(**kwargs)
```

Ключевое отличие: **`base_url` берётся из БД** (`app_config.llm_base_url`, кэш 60 с),
а не из литерала. Это делает проект единственным, где смена провайдера на агрегатор —
операция конфигурации, а не правка кода. Фабрика при этом знает только `"openai"`:

```python
def get_llm_gateway() -> LLMGateway:
    ...
    raise ValueError(f"Unknown LLM provider: ...")
```

След агрегатора, отличного от OpenRouter, тоже есть — тестовый скрипт
`scripts/test_yescale_api.py` для **YesScale** (OpenAI-совместимый агрегатор) с
захардкоженным ключом в дефолте env-переменной. Это одновременно и подтверждение
гибкости подхода, и проблема безопасности (ключ в репозитории).

---

## 5. Чего нет ни в одном проекте

Проверено по всем 6: агрегаторная тема в репозитории покрыта на минимальном уровне.

| Возможность | Есть? | Комментарий |
|---|---|---|
| Заголовки атрибуции агрегатора (`HTTP-Referer`, `X-Title`) | **нет нигде** | Упущение в обоих местах вызова OpenRouter |
| Официальный SDK OpenRouter (`openrouter`) | **нет** | Не используется ни в одном проекте |
| LiteLLM (библиотека или прокси) | **нет** | Только устаревший докстринг `agent_factory.py:3` и глушение логгера `litellm` в Quorum |
| Portkey / Together / Novita как шлюз | **нет** | — |
| `provider`-объект OpenRouter (`order`, `allow_fallbacks`, `sort`) | **нет** | Вызовы идут «как есть», без настройки маршрутизации |
| `models: [...]` — встроенный fallback-список OpenRouter | **нет** | Fallback-модель есть только в RAG-чатботе, своей реализацией |
| Retry/backoff на 429/5xx | почти нет | Единственное место — `normalizer.py` в RAG-чатботе, линейный backoff |
| Трекинг токенов/стоимости | 2 из 6 | Quorum (`TokenTrackingCallback`) и RAG-чатбот (Prometheus + `estimate_cost`) |

Вывод части: репозиторий интересен как набор **рабочих, но разных** способов выхода
к модели — «ручной HTTP» и «фреймворк-обёртка». Оба оставляют за бортом официальный SDK
агрегатора и его специфичные для роутинга параметры. Обзор всех современных вариантов
доступа — в Части 2.
