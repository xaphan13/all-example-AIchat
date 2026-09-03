# Руководство по аутентификации и авторизации в современных веб-приложениях (Часть 3: Внешние API и ключи)

В заключительной части нашего руководства мы рассмотрим специфический, но крайне популярный в эпоху LLM вид "аутентификации" — работу со сторонними API-ключами. Очень часто бэкенд выступает лишь прокси-сервером к мощным моделям от OpenAI, Anthropic или агрегаторам вроде OpenRouter.

Мы разберем, как эти механизмы реализованы в проектах **llm-council-karpathy** и **openai-responses-python-quickstart**.

---

## 1. Проксирование API-ключей (на примере llm-council-karpathy)

Проект **llm-council-karpathy** представляет собой систему из нескольких агентов, общающихся друг с другом. Бэкенд этого проекта использует агрегатор `OpenRouter` для доступа к различным LLM.

В данном случае аутентификация приложения (бэкенда) перед внешним сервисом осуществляется посредством передачи API-ключа в заголовке. Пользователи при этом не авторизуются, так как приложение предназначено для локального использования.

### Передача ключа в заголовках

В файле `../llm-council-karpathy/backend/openrouter.py` можно увидеть базовый паттерн проксирования:

```python
import os
import requests

# Ключ берется из переменных окружения (безопасное хранение)
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

def get_openrouter_response(messages, model="openai/gpt-4o"):
    headers = {
        # Стандартный формат передачи Bearer токена
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "HTTP-Referer": "http://localhost:3000", # Требование OpenRouter
        "X-Title": "LLM Council", # Требование OpenRouter
    }

    payload = {
        "model": model,
        "messages": messages
    }

    response = requests.post(OPENROUTER_URL, headers=headers, json=payload)
    return response.json()
```

Главное правило здесь: **никогда не хардкодить API-ключи в коде**. Ключ должен подтягиваться из файла `.env` (который, в свою очередь, добавлен в `../.gitignore`), чтобы избежать утечки секретов при пуше в публичный репозиторий.

---

## 2. Динамическое управление конфигурацией (на примере openai-responses-python-quickstart)

Проект **openai-responses-python-quickstart** имеет интересный роутер настройки (setup). Вместо того чтобы просто читать `env` файл, он предоставляет UI для динамического обновления конфигурации серверов Model Context Protocol (MCP). Это включает в себя передачу авторизационных токенов.

### Формирование конфигурации серверов

В `../openai-responses-python-quickstart/routers/setup.py` приложение собирает настройки из веб-формы. Важно отметить, что пользователи могут передать кастомные заголовки `authorization` для каждого MCP сервера.

```python
@router.post("/")
async def save_settings(
    request: Request,
    # ... другие поля формы ...
    mcp_authorizations: Annotated[list[str], Form(default_factory=list)],
):
    # ...
    for i in range(count):
        # Получаем токен из формы, если он есть
        authorization = get_or_empty(mcp_authorizations, i)

        entry = {
            "label": label,
            "url": url,
            "connection_type": connection_type,
        }

        # Динамически добавляем авторизацию к конфигурации
        if connection_type == "sse":
            if authorization:
                entry["authorization"] = authorization
    # ... сохранение конфигурации
```

### Безопасное логирование

При работе с внешними ключами и токенами важно следить за логами. Если вы просто распечатаете объект конфигурации или заголовки запроса в лог, ключи могут утечь в системы мониторинга.

В хороших проектах, подобных **Quorum** (см. `../Quorum/backend/src/infrastructure/logging/config.py`), настраиваются фильтры логирования, которые маскируют чувствительные данные:

```python
# Пример из Quorum/backend/src/infrastructure/logging/config.py
sensitive_keys = {"api_key", "token", "password", "secret", "authorization"}

# Функция-фильтр заменяет значения этих ключей на "***" перед выводом в консоль или файл.
```

## Вывод по Части 3

Работа с внешними API-ключами требует внимательного отношения к конфигурации и логированию.
1. Используйте `.env` файлы (или Secret Managers в облаке).
2. Маскируйте заголовки `Authorization` в логах.
3. В случае построения прокси (как в `llm-council-karpathy`), старайтесь, чтобы ключи хранились только на бэкенде, и никогда не отправляйте их на фронтенд клиентского приложения.

---
На этом наш цикл статей подошел к концу. Мы рассмотрели полноценные JWT системы, анонимные WebSocket сессии и безопасную работу с внешними ключами на реальных примерах из репозитория. Надеемся, этот гайд поможет вам спроектировать безопасную архитектуру вашего следующего веб-приложения!
