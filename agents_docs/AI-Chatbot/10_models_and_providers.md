# Модели и провайдеры AI

## 1. Короткий вывод

В текущем коде приложения реально настроена одна связка:

- **провайдер:** GitHub Models API;
- **API-контракт:** OpenAI-compatible Chat Completions;
- **endpoint:** `https://models.github.ai/inference/`;
- **модель:** `openai/gpt-4o`;
- **SDK:** Python-пакет `openai`, клиент `AsyncOpenAI`;
- **секрет:** `GITHUB_TOKEN` из `.env` или переменных окружения.

Остальные провайдеры и модели не подключены автоматически. Часть из них можно использовать через OpenAI-совместимый endpoint после изменения конфигурации, но доступность конкретной модели зависит от выбранного сервиса, аккаунта, лимитов и региона.

## 2. Фактическая конфигурация проекта

В `app/services/chat.py` сейчас используется:

```python
from openai import AsyncOpenAI

from app.core.config import settings

client = AsyncOpenAI(
    api_key=settings.GITHUB_TOKEN,
    base_url="https://models.github.ai/inference/",
)

response = await client.chat.completions.create(
    model="openai/gpt-4o",
    messages=[{"role": "user", "content": message}],
)
```

Важные свойства текущего варианта:

- `model` задан литералом и не читается из настроек;
- `base_url` также задан литералом;
- в конфигурации нет отдельных параметров `LLM_MODEL`, `LLM_BASE_URL`, `LLM_TIMEOUT` или `LLM_TEMPERATURE`;
- для API нужен GitHub-токен с правом доступа к моделям;
- приложение использует Chat Completions API, а не отдельные native SDK провайдеров.

## 3. Провайдер, используемый сейчас

### GitHub Models

GitHub Models предоставляет модели через endpoint, совместимый с популярными OpenAI SDK-паттернами. В приложении это позволяет использовать `AsyncOpenAI` и поменять `base_url` с OpenAI endpoint на GitHub endpoint.

| Параметр | Значение в проекте |
|---|---|
| Провайдер | GitHub Models |
| Base URL | `https://models.github.ai/inference/` |
| Модель | `openai/gpt-4o` |
| Авторизация | `GITHUB_TOKEN` |
| Клиент | `AsyncOpenAI` |
| Операция | `client.chat.completions.create` |

Пример переменной окружения:

```env
GITHUB_TOKEN=your_github_personal_access_token
```

В документации проекта это единственный провайдер, который считается подключённым фактически.

## 4. Что означает OpenAI-compatible API

Совместимый API обычно предоставляет похожую структуру вызова:

```python
client = AsyncOpenAI(
    api_key="provider-token",
    base_url="https://provider.example/v1",
)

response = await client.chat.completions.create(
    model="provider-model-name",
    messages=[
        {"role": "system", "content": "You are helpful."},
        {"role": "user", "content": "Hello"},
    ],
)
```

Для подключения такого провайдера в текущей архитектуре обычно достаточно:

1. указать другой `base_url`;
2. использовать подходящий API key;
3. заменить имя модели;
4. проверить поддерживаемые параметры (`stream`, `temperature`, `max_tokens`, tool calls);
5. проверить формат ошибок, лимиты и требования к авторизации.

Однако «совместимый» не означает полную идентичность. Некоторые сервисы поддерживают только часть параметров или используют собственные имена моделей.

## 5. Потенциальные варианты через тот же SDK

Следующие варианты **не включены в текущую конфигурацию**. Они показывают направления расширения.

### 5.1. OpenAI API

```python
from openai import AsyncOpenAI

client = AsyncOpenAI(
    api_key=settings.OPENAI_API_KEY,
    base_url="https://api.openai.com/v1",
)

response = await client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "Hello"}],
)
```

Потребуется добавить отдельную настройку ключа и модели. Нельзя использовать `GITHUB_TOKEN` как замену OpenAI API key без соответствующей авторизации.

### 5.2. Ollama локально

Ollama предоставляет локальный HTTP API с OpenAI-compatible режимом для поддерживаемых версий/настроек:

```python
from openai import AsyncOpenAI

client = AsyncOpenAI(
    api_key="ollama",
    base_url="http://localhost:11434/v1",
)

response = await client.chat.completions.create(
    model="llama3.1",
    messages=[{"role": "user", "content": "Hello"}],
)
```

Это потенциально позволяет выполнять модели локально без передачи текста внешнему провайдеру. Понадобятся установленный Ollama, загруженная модель и доступность сервиса из процесса FastAPI.

### 5.3. vLLM или другой self-hosted endpoint

Сервер, запущенный с OpenAI-compatible API, может вызываться тем же способом:

```python
client = AsyncOpenAI(
    api_key="local-or-service-token",
    base_url="http://llm-server:8000/v1",
)

response = await client.chat.completions.create(
    model="meta-llama/Llama-3.1-8B-Instruct",
    messages=[{"role": "user", "content": "Hello"}],
)
```

Нужно самостоятельно обеспечить GPU/CPU-ресурсы, безопасность endpoint, авторизацию, масштабирование, загрузку модели и наблюдаемость.

### 5.4. Azure OpenAI

Azure OpenAI использует совместимые с OpenAI операции, но требует особой схемы endpoint, deployment name и версии API:

```python
from openai import AsyncAzureOpenAI

client = AsyncAzureOpenAI(
    api_key=settings.AZURE_OPENAI_API_KEY,
    azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
    api_version="2024-10-21",
)

response = await client.chat.completions.create(
    model="my-gpt-deployment",
    messages=[{"role": "user", "content": "Hello"}],
)
```

Это не подключается к проекту заменой только значения `base_url`: понадобится отдельный клиент и настройки deployment/API version.

## 6. Провайдеры, которым нужен отдельный адаптер

### Anthropic

Anthropic имеет собственный Messages API и официальный SDK. Его формат ролей, параметры и путь вызова не полностью совпадают с текущим `client.chat.completions.create`. Для подключения потребуется:

- отдельный клиент/SDK или HTTP-адаптер;
- преобразование внутреннего формата сообщений;
- обработка специфичных полей ответа и ошибок;
- конфигурация Anthropic API key.

### Google Gemini

Gemini также имеет собственный SDK/API и собственные форматы content parts, safety settings и tool calling. Он может быть доступен через сторонние OpenAI-compatible шлюзы, но прямое подключение к Google API требует адаптера.

Следовательно, Anthropic и Gemini нельзя считать поддержанными текущим приложением только потому, что приложение использует пакет `openai`.

## 7. Примеры моделей

Ниже приведены классы моделей, которые могут встречаться у провайдеров. Это **не список уже доступных моделей проекта**:

| Семейство/пример | Возможный канал | Статус в приложении |
|---|---|---|
| `openai/gpt-4o` | GitHub Models | Задано в коде |
| `gpt-4o` | OpenAI или совместимый шлюз | Не подключено |
| `meta-llama/Llama-3.1-8B-Instruct` | vLLM, Ollama, другой сервер | Не подключено |
| `llama3.1` | Ollama | Не подключено |
| модели семейства Mistral | GitHub Models, hosted/self-hosted сервисы | Не подключено |
| модели Anthropic Claude | Anthropic API | Нужен отдельный адаптер |
| модели Google Gemini | Google API | Нужен отдельный адаптер |

Точное имя модели нужно брать из каталога конкретного провайдера. Нельзя гарантировать, что модель доступна по одному и тому же имени в GitHub Models, OpenAI, Ollama и self-hosted сервере.

## 8. Как вынести провайдера и модель в настройки

Рекомендуемое направление для будущего рефакторинга `app/core/config.py`:

```python
class Setting(BaseSettings):
    DATABASE_URL: str = "sqlite+aiosqlite:///./sqlite.db"
    GITHUB_TOKEN: str = ""
    LLM_API_KEY: str = ""
    LLM_BASE_URL: str = "https://models.github.ai/inference/"
    LLM_MODEL: str = "openai/gpt-4o"
    LLM_TIMEOUT: float = 30.0
    LLM_TEMPERATURE: float = 0.7
```

И сервис:

```python
from openai import AsyncOpenAI

from app.core.config import settings

client = AsyncOpenAI(
    api_key=settings.LLM_API_KEY or settings.GITHUB_TOKEN,
    base_url=settings.LLM_BASE_URL,
    timeout=settings.LLM_TIMEOUT,
)


async def get_chat_response(prompt: str) -> str:
    response = await client.chat.completions.create(
        model=settings.LLM_MODEL,
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": prompt},
        ],
        temperature=settings.LLM_TEMPERATURE,
    )
    return response.choices[0].message.content or ""
```

Перед внедрением нужно проверить совместимость провайдера с каждым используемым параметром. Также желательно не смешивать универсальные настройки с секретами: API keys должны иметь отдельные имена (`GITHUB_TOKEN`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY` и т. п.).

## 9. Рекомендации по выбору

- **Для текущего MVP:** оставить GitHub Models и добавить конфигурацию модели, timeout и обработку ошибок.
- **Для экспериментов без внешней передачи данных:** рассмотреть Ollama или self-hosted vLLM.
- **Для production через управляемый сервис:** выбирать провайдера по SLA, лимитам, региону, стоимости и политике хранения данных.
- **Для нескольких провайдеров:** ввести абстракцию `LLMProvider` и адаптеры, а не разбрасывать условные проверки по endpoint.
- **Для мультиагентности:** заранее определить, какие агенты используют одну модель, а какие — разные модели, и где хранятся промежуточные результаты.

## 10. Итог

Сейчас приложение поддерживает одну фактическую конфигурацию — GitHub Models API с моделью `openai/gpt-4o`. Благодаря OpenAI-compatible интерфейсу архитектура допускает подключение других совместимых endpoint, но это потребует конфигурационных изменений и проверки совместимости. Провайдеры с собственными API, включая Anthropic и Google Gemini, требуют отдельных адаптеров. Выбор новой модели сам по себе не добавляет приложению память, инструменты или мультиагентность — это отдельные архитектурные возможности.
