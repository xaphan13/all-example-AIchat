# Способы доступа к агрегаторам моделей: библиотеки и примеры кода (Часть 2)

> Дата: 21.09.2026
> Источники: официальная документация OpenRouter, LiteLLM, Pydantic AI, OpenAI SDK,
> Instructor, Portkey (проверено 21.09.2026) + код репозитория.
> Часть 2 из 3. Часть 1 — инвентаризация проектов, Часть 3 — надёжность и практика.

## 1. Почему агрегаторы вообще подключаются «одной строкой»

Агрегатор даёт **один API и один ключ** к моделям многих вендоров. Практически все
современные агрегаторы реализуют **OpenAI-совместимый вход** — то есть
`POST /v1/chat/completions` с телом, идентичным OpenAI. Отсюда четыре независимых
способа доступа, от самого ручного до самого высокоуровневого:

| # | Способ | Что вы получаете | Что теряете |
|---|---|---|---|
| 1 | Ручной HTTP (`httpx`/`requests`) | полный контроль над телом и заголовками | типизацию, retry, стриминг-хелперы |
| 2 | OpenAI SDK + `base_url` | вся зрелость SDK: retry, таймауты, стриминг | специфику агрегатора (нужны `default_headers`/`extra_body`) |
| 3 | Официальный SDK агрегатора (`openrouter`) | типы, сгенерированные из OpenAPI | привязка к одному вендору-агрегатору |
| 4 | Универсальная библиотека (LiteLLM) | 100+ провайдеров одним интерфейсом, Router с fallback/retry | лишний слой абстракции и зависимости |
| 5 | Фреймворк агентов (LangChain, Pydantic AI, Instructor) | структурированный вывод, агенты, телеметрия | вес фреймворка, «магию» под капотом |
| 6 | Отдельный шлюз-прокси (LiteLLM Proxy, Portkey) | ключи, бюджеты, кэш, лимиты вне кода | отдельный сервис в инфраструктуре |

Разница между агрегатором и прокси-шлюзом: агрегатор — внешний сервис, роутер —
ваш (или чужой) посредник, который тоже говорит на OpenAI-протоколе. С точки зрения
клиентского кода это одно и то же: `base_url` + ключ.

---

## 2. Способ 1: ручной HTTP-запрос

Самый честный способ. Полезен, когда нужно использовать недокументированные поля
агрегатора или не тянуть зависимости.

```python
import os
import httpx

client = httpx.AsyncClient(
    base_url="https://openrouter.ai/api/v1",
    timeout=httpx.Timeout(120.0, connect=5.0),
    headers={
        "Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}",
        "HTTP-Referer": "https://myapp.example.com",   # атрибуция приложения
        "X-OpenRouter-Title": "My App",
    },
)

async def ask(model: str, messages: list[dict]) -> str:
    response = await client.post("/chat/completions",
                                 json={"model": model, "messages": messages})
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]
```

**Стриминг вручную** (SSE):

```python
async with client.stream("POST", "/chat/completions",
                         json={"model": model, "messages": messages, "stream": True}) as r:
    async for line in r.aiter_lines():
        if not line.startswith("data: "):
            continue
        payload = line[6:]
        if payload == "[DONE]":
            break
        print(json.loads(payload)["choices"][0]["delta"].get("content", ""), end="")
```

Именно так делает `llm-council-karpathy` — но без переиспользования клиента и без
заголовков атрибуции (см. Часть 1, раздел 2).

**Когда выбирать:** разовый скрипт, диагностика, нестандартные поля агрегатора,
нежелание добавлять SDK. **Когда не стоит:** продукт — вручную придётся реализовать
retry, таймауты, стриминг, типы, обновление формата.

---

## 3. Способ 2: OpenAI SDK с подменённым `base_url`

Самый распространённый способ в индустрии и самый «дешёвый» по усилиям:
у вас уже есть код на OpenAI SDK, нужно поменять две строки.

```python
from openai import AsyncOpenAI

client = AsyncOpenAI(
    api_key=os.environ["OPENROUTER_API_KEY"],
    base_url="https://openrouter.ai/api/v1",
    default_headers={
        "HTTP-Referer": "https://myapp.example.com",
        "X-OpenRouter-Title": "My App",
    },
    timeout=30.0,        # дефолт SDK — 10 минут, для чата это слишком много
    max_retries=3,       # дефолт SDK — 2
)

response = await client.chat.completions.create(
    model="anthropic/claude-sonnet-4.5",
    messages=[{"role": "user", "content": "Привет"}],
)
```

**Что SDK делает автоматически** (важно и часто забывается):

- повторяет запрос **2 раза** по умолчанию с коротким экспоненциальным backoff;
- повторяет: ошибки соединения, **408**, **409**, **429**, любые **>= 500**;
- **не повторяет** уже начатое потребление стрима (иначе дублировался бы вывод);
- `APITimeoutError` при превышении `timeout`, таймаут-запросы ретраятся дважды;
- `base_url` можно задать переменной `OPENAI_BASE_URL`, ключ — `OPENAI_API_KEY`.

**Провайдеро-специфичные поля** передаются через `extra_body`:

```python
response = await client.chat.completions.create(
    model="meta-llama/llama-3.3-70b-instruct",
    messages=messages,
    extra_body={"provider": {"order": ["together"], "allow_fallbacks": False}},
)
```

Этот способ в репозитории реализован в трёх проектах (AI-Chatbot — GitHub Models,
RAG-чатбот — конфигурируемый `base_url`, openai-responses — но там Responses API,
а не Chat Completions). Ни в одном из них не передаются `default_headers` или
`max_retries` — то есть используется «голый» SDK.

---

## 4. Способ 3: официальный SDK агрегатора

Относительно новое явление. У OpenRouter **есть официальные клиентские SDK**:

| Язык | Пакет | Установка |
|---|---|---|
| Python | `openrouter` | `pip install openrouter` |
| TypeScript/JS | `@openrouter/sdk` | `npm install @openrouter/sdk` |

```python
from openrouter import OpenRouter
import os

with OpenRouter(
    api_key=os.getenv("OPENROUTER_API_KEY"),
    http_referer="https://myapp.example.com",  # атрибуция приложения
    app_title="My App",
) as client:
    response = client.chat.send(
        model="anthropic/claude-sonnet-4.5",
        messages=[{"role": "user", "content": "Привет"}],
    )
    print(response.choices[0].message.content)
```

Документация OpenRouter описывает SDK как **«намеренно тонкий слой поверх REST API»**:
типы автоматически генерируются из OpenAPI-спецификации, поэтому доступны все поля
агрегатора. Рекомендация вендора: **использовать SDK по умолчанию**, а OpenAI SDK с
`base_url` — только если у вас уже есть код на OpenAI SDK («drop-in replacement»).

Есть и отдельный пакет для агентов — `@openrouter/agent` (пока только для TS).

**Плюсы:** типобезопасность, атрибуция из коробки, все специфичные для роутинга поля
первоклассные. **Минус:** привязка к одному вендору-агрегатору; переезд на другой
агрегатор — это переписывание слоя доступа.

**В репозитории этот SDK не используется** ни в одном проекте — на момент написания
цикла это самая заметная незакрытая возможность.

---

## 5. Способ 4: LiteLLM — универсальный интерфейс к 100+ провайдерам

LiteLLM — open-source библиотека, дающая **один интерфейс в формате OpenAI** к
100+ провайдерам: OpenAI, Anthropic, Vertex AI, Bedrock и прочим. Поддерживает и
агрегаторы. Ключевая идея — префикс провайдера в имени модели.

### 5.1. Прямой вызов

```python
import os
from litellm import completion

# Для OpenRouter:
os.environ["OPENROUTER_API_KEY"] = "sk-or-..."
os.environ["OPENROUTER_API_BASE"] = "https://openrouter.ai/api/v1"  # опционально
os.environ["OR_SITE_URL"] = "https://myapp.example.com"   # атрибуция
os.environ["OR_APP_NAME"] = "My App"                      # атрибуция

response = completion(
    model="openrouter/anthropic/claude-sonnet-4.5",   # агрегатор/вендор/модель
    messages=[{"role": "user", "content": "Привет"}],
)
print(response.choices[0].message.content)
```

Формат префикса для агрегатора — `openrouter/<vendor>/<model>`. А для прямых
провайдеров — просто `<provider>/<model>`:

```python
completion(model="anthropic/claude-sonnet-5", messages=messages)
completion(model="openai/gpt-5.6-terra", messages=messages)
completion(model="ollama/llama3", messages=messages, api_base="http://localhost:11434")
```

Ответ во всех случаях — **единый формат** (объект в стиле OpenAI), независимо от
вендора. Это главная ценность: код выше `completion()` не переписывается при смене
провайдера.

### 5.2. Router: fallback, retry, балансировка

`litellm.Router` — слой над `completion()` с маршрутизацией, повторами и
резервированием между несколькими развёртываниями/моделями. Это то, чего нет ни в
одном проекте репозитория.

```python
from litellm import Router

router = Router(
    model_list=[
        {"model_name": "fast",
         "litellm_params": {"model": "openrouter/openai/gpt-4o-mini",
                            "api_key": os.environ["OPENROUTER_API_KEY"]}},
        {"model_name": "fast",   # то же логическое имя = второе развёртывание
         "litellm_params": {"model": "openrouter/google/gemini-3-flash-preview",
                            "api_key": os.environ["OPENROUTER_API_KEY"]}},
    ],
    num_retries=3,
    fallbacks=[{"fast": ["openrouter/anthropic/claude-sonnet-4.5"]}],
)

response = router.completion(
    model="fast",
    messages=[{"role": "user", "content": "Привет"}],
)
```

Несколько записей с одинаковым `model_name` = пул развёртываний с балансировкой;
`fallbacks` задаёт, куда уходить при отказе; `num_retries` — бюджет повторов.

### 5.3. LiteLLM Proxy — отдельный сервис

Если не хочется тащить библиотеку в приложение, LiteLLM поднимается как
**self-hosted OpenAI-совместимый шлюз**. Тогда любой OpenAI-клиент работает без
единой правки кода:

```yaml
# litellm_config.yaml
model_list:
  - model_name: council
    litellm_params:
      model: openrouter/google/gemini-3-pro-preview
      api_base: os.environ/OPENROUTER_API_BASE
      api_key: os.environ/OPENROUTER_API_KEY
```

```bash
docker run -v $(pwd)/litellm_config.yaml:/app/config.yaml \
  -e OPENROUTER_API_KEY=sk-or-... -p 4000:4000 \
  docker.litellm.ai/berriai/litellm:latest --config /app/config.yaml
```

```python
import openai
client = openai.OpenAI(api_key="anything", base_url="http://localhost:4000")
client.chat.completions.create(model="council", messages=messages)
```

Прокси даёт виртуальные ключи, бюджеты, трекинг расходов и админ-панель — то есть
выносит всю работу с провайдерами из приложения в инфраструктуру.

---

## 6. Способ 5: фреймворки агентов поверх агрегатора

### 6.1. LangChain `ChatOpenAI`

Именно этот способ уже применён в Quorum: `langchain_openai.ChatOpenAI` с
`base_url` агрегатора. Он даёт `BaseChatModel`-интерфейс, `astream`, `callbacks`
и возможность заменить провайдера, не меняя код агентов. При необходимости заголовки
атрибуции добавляются явно:

```python
from langchain_openai import ChatOpenAI

model = ChatOpenAI(
    model="anthropic/claude-sonnet-4.5",
    base_url="https://openrouter.ai/api/v1",
    api_key=os.environ["OPENROUTER_API_KEY"],
    default_headers={"HTTP-Referer": "https://myapp.example.com",
                     "X-OpenRouter-Title": "My App"},
    timeout=30,
    max_retries=3,
)

async for chunk in model.astream("Привет"):
    print(chunk.content, end="")
```

Практический вывод для Quorum: `default_headers`, `timeout` и `max_retries` —
три параметра, добавление которых «включает» атрибуцию и надёжность без смены
архитектуры.

### 6.2. Pydantic AI — типизированные агенты

```python
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIChatModel   # именно так, не OpenAIModel
from pydantic_ai.providers.openai import OpenAIProvider

model = OpenAIChatModel(
    "model_name",
    provider=OpenAIProvider(
        base_url="https://openrouter.ai/api/v1",
        api_key="sk-or-...",
    ),
)
agent = Agent(model, output_type=Answer)
```

У Pydantic AI есть **отдельный класс провайдера для OpenRouter**
(`pydantic_ai.providers.openrouter.OpenRouterProvider`) и шорткат-строка
`Agent("openrouter:openai/gpt-5.6-sol")`. Отдельно отмечен нюанс, важный для агрегаторов:
флаг `openai_chat_supports_max_completion_tokens=False` нужен провайдерам (например,
OpenRouter), которые принимают только старый `max_tokens`, а не
`max_completion_tokens`.

### 6.3. Instructor — структурированный вывод

```python
import instructor
from pydantic import BaseModel

class User(BaseModel):
    name: str
    age: int

client = instructor.from_provider(
    "openrouter/google/gemini-3-flash-preview",
    base_url="https://openrouter.ai/api/v1",
    async_client=True,
)

user = await client.create(
    messages=[{"role": "user", "content": "Иван, 28 лет"}],
    response_model=User,
    extra_body={"provider": {"require_parameters": True}},
)
```

`require_parameters: True` здесь не украшение: он заставляет агрегатор **выбрать только
тех провайдеров, которые поддерживают все параметры запроса** — иначе structured output
может молча деградировать на движке, который его не умеет. По умолчанию Instructor
использует tool calling; если модель его не поддерживает — советует JSON-режим.
Стриминг частичных объектов — `client.create_partial(...)`.

---

## 7. Способ 6: отдельный шлюз-прокси (Portkey и аналоги)

Portkey AI Gateway (сейчас также известен как Prisma AIRS AI Gateway) — **унифицированный
интерфейс к 250+ моделям**, работает как прокси через тот же OpenAI SDK:

```python
from openai import OpenAI
from portkey_ai import PORTKEY_GATEWAY_URL, createHeaders

client = OpenAI(
    api_key="YOUR_OPENAI_API_KEY",
    base_url=PORTKEY_GATEWAY_URL,
    default_headers=createHeaders(
        provider="openai",
        api_key="YOUR_PORTKEY_API_KEY",
    ),
)
```

REST-вариант — свой заголовок провайдера:

```bash
curl https://api.portkey.ai/v1/chat/completions \
  -H "x-portkey-api-key: YOUR_PORTKEY_API_KEY" \
  -H "x-portkey-provider: openrouter" \
  -d '{"model": "...", "messages": [...]}'
```

Обратите внимание на паттерн `createHeaders(provider=..., api_key=...)`: клиент остаётся
«обычным OpenAI-клиентом», а провайдер и его ключ подставляются **заголовками**. Это
удобный способ отвязать код от конкретного провайдера вообще.

Portkey заявляет latency ~20–40 мс поверх прямого вызова, соответствие
ISO:27001/SOC 2/GDPR/HIPAA, опциональный отказ от хранения тел запросов; gateway
open-source и бесплатен, managed-план — 10 тыс. запросов/месяц.

---

## 8. Связанный набор: параметры роутинга у OpenRouter

Отдельная ценность агрегатора, недоступная при прямых вызовах вендоров. Всё
передаётся объектом `provider` в теле запроса (или через `extra_body` из SDK):

```json
{
  "model": "mistralai/mixtral-8x7b-instruct",
  "messages": [{"role": "user", "content": "Привет"}],
  "provider": {
    "order": ["openai", "together"],
    "allow_fallbacks": false,
    "require_parameters": true,
    "data_collection": "deny",
    "sort": {"by": "price", "partition": "none"}
  }
}
```

Ключевые поля: `order` (порядок провайдеров), `allow_fallbacks` (разрешить резервных),
`require_parameters` (только поддерживающие все параметры), `data_collection: "deny"`
(только не собирающие данные), `zdr` (Zero Data Retention), `only`/`ignore`,
`quantizations`, `sort` по `price`/`throughput`/`latency`, `max_price`.

**Fallback-список моделей** задаётся не полем `model`, а массивом `models`:

```json
{
  "models": ["anthropic/claude-sonnet-4.5", "openai/gpt-5-mini", "google/gemini-3-flash-preview"],
  "messages": [{"role": "user", "content": "Привет"}],
  "provider": {"sort": {"by": "price", "partition": "none"}}
}
```

Это встроенный в агрегатор аналог `fallbacks` у LiteLLM Router — и его нет ни в одном
проекте репозитория.

**Суффиксы быстрого выбора:** `:nitro` в имени модели = сортировка по пропускной
способности (плюс доступ к priority-tier), `:floor` = по цене (плюс flex-tier):

```json
{"model": "meta-llama/llama-3.3-70b-instruct:nitro", "messages": [...]}
```

---

## 9. Итоговая таблица сравнения способов

| Способ | Строк до первого ответа | Вендор-нейтральность | Retry/fallback | Типы | Вес зависимости |
|---|---|---|---|---|---|
| `httpx` вручную | ~10 | полная | сам | нет | минимальный |
| OpenAI SDK + `base_url` | ~5 | высокая | **есть** (2× по умолчанию) | есть | средний |
| SDK OpenRouter | ~5 | низкая (вендор-агрегатор) | есть | есть | средний |
| LiteLLM (`completion`) | ~4 | **максимальная** (100+) | через Router | есть | большой |
| LiteLLM Proxy | ~3 | максимальная | через конфиг | — | отдельный сервис |
| LangChain `ChatOpenAI` | ~8 | высокая | параметрами | есть | большой |
| Pydantic AI | ~8 | высокая | параметрами | сильная (Pydantic) | большой |
| Instructor | ~8 | высокая | параметрами | сильная | средний |
| Portkey (прокси) | ~8 | максимальная | на стороне шлюза | — | внешний сервис |

**Практические рекомендации по выбору:**

1. **Разовый скрипт / диагностика** — `httpx` или `curl`-эквивалент.
2. **Продукт на Python, один агрегатор** — OpenAI SDK + `base_url` + `default_headers`
   + явные `timeout`/`max_retries`. Минимум кода и максимум зрелости.
3. **Продукт, где важна типобезопасность и атрибуция** — официальный SDK агрегатора.
4. **Много провайдеров или агрегаторов сразу** — LiteLLM (библиотекой или прокси).
5. **Агенты и структурированный вывод** — LangChain/Pydantic AI/Instructor поверх
   агрегатора (как в Quorum), с явной настройкой профилей под нюансы агрегатора.
6. **Организационные требования (ключи, бюджеты, аудит вне кода)** — отдельный шлюз
   (LiteLLM Proxy или Portkey).

Практика надёжности — таймауты, повторы, fallback, подсчёт стоимости, безопасность
ключей — разобрана в Части 3.
