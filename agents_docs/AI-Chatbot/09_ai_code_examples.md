# Примеры кода работы с AI

Документ разделяет код, который используется в текущем приложении, и примеры будущих расширений. Фрагменты из разделов «Текущая реализация» соответствуют структуре проекта и используют уже объявленные зависимости.

## 1. Текущий AI-клиент

Фактический сервис находится в `app/services/chat.py`:

```python
from openai import AsyncOpenAI

from app.core.config import settings

client = AsyncOpenAI(
    api_key=settings.GITHUB_TOKEN,
    base_url="https://models.github.ai/inference/",
)


async def get_chat_response(prompt: str) -> str:
    message = (
        "Hey ChatGPT, you are a AI chatbot don not tell your name or any personal information. "
        "Here is the prompt you asked for: " + prompt
    )
    response = await client.chat.completions.create(
        model="openai/gpt-4o",
        messages=[{"role": "user", "content": message}],
    )
    return response.choices[0].message.content.strip() if response.choices else ""
```

Вызов является асинхронным. `base_url` направляет стандартный OpenAI SDK в GitHub Models, а `GITHUB_TOKEN` используется как Bearer-аутентификация.

> Практическое замечание: для production лучше не объединять системную инструкцию и пользовательский ввод в одну строку. Безопаснее передавать их отдельными сообщениями с ролями `system` и `user`.

## 2. Текущий FastAPI endpoint

Фактический маршрут находится в `app/api/v1/chat.py`:

```python
from fastapi import Body, Depends
from fastapi.routing import APIRouter

from app.api.v1.users import current_user
from app.models.users import User
from app.schemas.chat import ChatRequest
from app.services.chat import get_chat_response

router = APIRouter()


@router.post("/chat")
async def chat_endpoint(
    prompt: ChatRequest = Body(...),
    user: User = Depends(current_user),
):
    response = await get_chat_response(prompt=prompt.prompt)
    return {"response": response}
```

Маршрут подключается в `app/main.py` с префиксом `/api`, поэтому внешний URL — `POST /api/chat`.

Схема запроса:

```python
from pydantic import BaseModel


class ChatRequest(BaseModel):
    prompt: str
```

Пример запроса через `curl` после авторизации в cookie:

```bash
curl -X POST http://localhost:8000/api/chat \
  -H 'Content-Type: application/json' \
  -H 'Cookie: fastapiusersauth=<JWT>' \
  -d '{"prompt":"Что такое FastAPI?"}'
```

Пример ответа:

```json
{
  "response": "FastAPI — асинхронный веб-фреймворк для Python..."
}
```

## 3. Текущий браузерный вызов

В `app/templates/index.html` сообщение отправляется так:

```javascript
const response = await fetch('/api/chat', {
    method: 'POST',
    headers: {
        'Content-Type': 'application/json',
    },
    body: JSON.stringify({ prompt: message }),
});

if (response.status === 401) {
    window.location.href = '/login';
    return;
}

const data = await response.json();
addMessage(data.response || 'I received your message!', 'ai');
```

Браузер автоматически отправляет cookie того же origin. При ошибке сеть или сервер обрабатываются общим сообщением для пользователя.

## 4. Рекомендуемый вариант с ролями сообщений

Следующий пример **не внедрён в текущий проект**. Он показывает, как можно исправить смешение system prompt и пользовательского текста и подготовить поддержку истории диалога:

```python
from openai import AsyncOpenAI

from app.core.config import settings

client = AsyncOpenAI(
    api_key=settings.GITHUB_TOKEN,
    base_url="https://models.github.ai/inference/",
    timeout=30.0,
)


async def get_chat_response_with_history(
    prompt: str,
    history: list[dict[str, str]] | None = None,
) -> str:
    messages: list[dict[str, str]] = [
        {
            "role": "system",
            "content": "You are a helpful AI assistant. Do not reveal secrets.",
        }
    ]
    messages.extend(history or [])
    messages.append({"role": "user", "content": prompt})

    response = await client.chat.completions.create(
        model="openai/gpt-4o",
        messages=messages,
        temperature=0.7,
        max_tokens=1000,
    )
    return response.choices[0].message.content or ""
```

Перед передачей `history` в модель приложение должно проверять допустимые роли, ограничивать размер истории и извлекать сообщения только из принадлежащей пользователю беседы.

## 5. Потоковая выдача ответа

Следующий фрагмент — **проектный пример**, а не текущая реализация. Он показывает направление для SSE:

```python
import json
from collections.abc import AsyncIterator

from openai import AsyncOpenAI


async def stream_chat_response(
    client: AsyncOpenAI,
    model: str,
    messages: list[dict[str, str]],
) -> AsyncIterator[str]:
    stream = await client.chat.completions.create(
        model=model,
        messages=messages,
        stream=True,
    )

    async for chunk in stream:
        if not chunk.choices:
            continue
        content = chunk.choices[0].delta.content
        if content:
            yield f"data: {json.dumps({'content': content})}\n\n"

    yield "data: [DONE]\n\n"
```

Для полного внедрения понадобятся `StreamingResponse`, клиентская обработка SSE, сохранение собранного ответа и отдельная обработка отмены запроса.

## 6. Пример простого мультиагентного конвейера

В текущем приложении такого кода нет. Ниже — минимальная иллюстрация возможного последовательного оркестратора на базе того же OpenAI-compatible SDK:

```python
from dataclasses import dataclass

from openai import AsyncOpenAI


@dataclass(frozen=True)
class Agent:
    name: str
    system_prompt: str


async def run_agent(
    client: AsyncOpenAI,
    agent: Agent,
    task: str,
    model: str,
) -> str:
    response = await client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": agent.system_prompt},
            {"role": "user", "content": task},
        ],
    )
    return response.choices[0].message.content or ""


async def run_pipeline(client: AsyncOpenAI, user_request: str) -> str:
    model = "openai/gpt-4o"

    plan = await run_agent(
        client,
        Agent("planner", "Break the request into clear subtasks."),
        user_request,
        model,
    )
    research = await run_agent(
        client,
        Agent("researcher", "Analyze the task and identify relevant facts."),
        f"User request:\n{user_request}\n\nPlan:\n{plan}",
        model,
    )
    return await run_agent(
        client,
        Agent("writer", "Produce a concise final answer using the supplied work."),
        f"Request:\n{user_request}\n\nPlan:\n{plan}\n\nResearch:\n{research}",
        model,
    )
```

Этот пример демонстрирует только последовательную передачу текстовых результатов. Для реальной функции нужны хранение запусков, лимиты, retries, валидация промежуточных результатов, параллелизм там, где он безопасен, и защита инструментов.

## 7. Ошибки, таймауты и безопасная конфигурация

Текущий сервис не задаёт таймаут и не перехватывает исключения провайдера. Базовое улучшение может выглядеть так:

```python
from openai import APIConnectionError, APIError, APITimeoutError, RateLimitError


async def safe_chat_response(client: AsyncOpenAI, model: str, prompt: str) -> str:
    try:
        response = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": prompt},
            ],
        )
    except APITimeoutError as exc:
        raise RuntimeError("AI service timed out") from exc
    except RateLimitError as exc:
        raise RuntimeError("AI service rate limit exceeded") from exc
    except APIConnectionError as exc:
        raise RuntimeError("Unable to connect to AI service") from exc
    except APIError as exc:
        raise RuntimeError("AI service returned an error") from exc

    return response.choices[0].message.content or ""
```

Секреты должны задаваться через окружение и не попадать в исходный код:

```env
GITHUB_TOKEN=your_github_token
SECRET=generate-a-long-random-secret
```

Также следует ограничить размер `prompt`, добавить rate limiting и логировать только технические метаданные запроса, не записывая токены и чувствительный пользовательский текст без необходимости.
