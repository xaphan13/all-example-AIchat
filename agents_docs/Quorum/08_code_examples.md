# 08 — Примеры кода работы с AI

> Реальные фрагменты из проекта NoOversight / Quorum, показывающие интеграцию с LLM.
> Все примеры выдержаны из текущей кодовой базы (август 2026).
> Формат файлов/путей: `backend/src/...`.

---

## 1. Создание LLM-клиента (LangChain → OpenRouter)

Основа всей работы с моделями — инициализация `ChatOpenAI` с `base_url` OpenRouter
и callback'ом трекинга токенов.

```python
# backend/src/agents/base_agent.py:98-108
from langchain_openai import ChatOpenAI

chat_model = ChatOpenAI(
    model=model_name,                    # например "anthropic/claude-3.5-sonnet"
    temperature=self.config.temperature,
    max_tokens=self.config.max_tokens,
    api_key=openrouter_key,              # из SettingsService (БД → env fallback)
    base_url="https://openrouter.ai/api/v1",
    callbacks=callbacks,                 # [TokenTrackingCallback(...)]
    **tool_kwargs                        # {"tools": [...]} если зарегистрированы tools
)
```

Ключ берётся каскадно (`backend/src/core/settings_service.py`):

```python
openrouter_key = await self._settings_service.get_openrouter_api_key()
# приоритет: app_settings (БД) → окружение OPENROUTER_API_KEY
```

---

## 2. Потоковая генерация (token-by-token)

Streaming-режим, на котором построен весь UI: каждый токен уходит клиенту по WebSocket.

```python
# backend/src/agents/base_agent.py:171-188
async for chunk in chat_model.astream(langchain_messages):
    if chunk.content:
        content = chunk.content
        accumulated_content += content

        yield StreamChunk(
            agent_id=self.config.agent_id,
            content=content,
            is_final=False
        )

# Финальный чанк-маркер
yield StreamChunk(
    agent_id=self.config.agent_id,
    content="",
    is_final=True,
    metadata={"total_length": len(accumulated_content)}
)
```

Конвертация OpenAI-формата сообщений в объекты LangChain:

```python
# backend/src/agents/base_agent.py:296-307
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

for msg in messages:
    role = msg.get("role", "user")
    content = msg.get("content", "")

    if role == "system":
        langchain_messages.append(SystemMessage(content=content))
    elif role == "assistant":
        langchain_messages.append(AIMessage(content=content))
    else:
        langchain_messages.append(HumanMessage(content=content))
```

---

## 3. Non-streaming вызов (служебные шаги)

Используется там, где нужен целый ответ одной строкой — например, для JSON-плана
делегирования.

```python
# backend/src/agents/base_agent.py:255-256
response = await chat_model.ainvoke(langchain_messages)
content = response.content
```

---

## 4. Создание агентов через фабрику

```python
# backend/src/agents/agent_factory.py:22-26
MODEL_MAP = {
    AgentType.CLAUDE_MAIN: "anthropic/claude-3.5-sonnet",  # main orchestrator
    AgentType.CLAUDE_SUB: "anthropic/claude-3-5-haiku",    # fast, efficient
    AgentType.GPT5: "openai/gpt-4o",                       # balanced reasoning
}
```

Main-агент (оркестратор):

```python
# backend/src/core/orchestrator/task_orchestrator.py:189
self.main_agent = AgentFactory.create_main_agent(session_id=self.session_id)
```

Суб-агент под конкретную подзадачу (дописывает task в system prompt):

```python
# backend/src/core/orchestrator/task_orchestrator.py:457-461
agent = AgentFactory.create_sub_agent(
    agent_type=agent_type,
    task_description=query_spec["query"],
    session_id=self.session_id
)
```

---

## 5. Инструменты: регистрация и вызов web_search

Рабочий пример из `backend/examples/web_search_example.py` — можно запустить как есть
(`cd backend && python examples/web_search_example.py`).

```python
# backend/examples/web_search_example.py:20-41
from src.agents.agent_factory import AgentFactory
from src.core.models import AgentType
from src.tools.registry import ToolRegistry
from src.tools.web_search import WebSearchTool

registry = ToolRegistry()
registry.register(WebSearchTool(provider="duckduckgo"))  # без API-ключа

agent = AgentFactory.create_agent(
    agent_type=AgentType.CLAUDE_MAIN,
    tool_registry=registry
)

result = await agent.execute_tool(
    "web_search",
    query="latest AI developments 2024",
    num_results=3
)

if result.success:
    for item in result.data['results']:
        print(item['title'], item['url'])
```

Генерация OpenAI function-calling схемы для передачи в LLM (`backend/src/tools/base.py:73-105`):

```python
schema = web_search.get_schema()
# → {"name": "web_search", "description": "...",
#    "parameters": {"type": "object", "properties": {...}, "required": ["query"]}}
```

> Примечание: схемы передаются в `ChatOpenAI(tools=...)`, но автоматическое выполнение
> tool calls из ответа модели пока не реализовано. Рабочий способ — прямой
> `agent.execute_tool(...)`, как в примере выше (см. `docs/04`).

---

## 6. Мульти-агентная конференция (см. также docs/09)

Решение о делегировании — non-streaming запрос к main-агенту с обязательным JSON:

```python
# backend/src/core/orchestrator/task_orchestrator.py:380-389
response = await self.main_agent.get_complete_response(messages)

if "```json" in response:
    response = response.split("```json")[1].split("```")[0].strip()
elif "```" in response:
    response = response.split("```")[1].split("```")[0].strip()

delegation_plan = json.loads(response)
# {"delegate": true, "sub_queries": [{"agent_type": "gpt-5", "query": "...", "priority": 1}]}
```

Раунды обсуждения: каждый агент стримит, видя ответы предыдущих раундов:

```python
# backend/src/core/orchestrator/task_orchestrator.py:653-672
messages = [
    {"role": "system", "content": agent.config.system_prompt},
    {"role": "user", "content": prompt}   # контекст всех предыдущих раундов
]

async for chunk in agent.stream_response(messages):
    if chunk.content and not chunk.is_final:
        response_content += chunk.content
        yield {
            "type": "agent_message_chunk",
            "messageId": message_id,
            "agentId": agent_id,
            "content": chunk.content,
            "roundNumber": current_round,
            "isComplete": False,
            ...
        }
```

---

## 7. API-слой: WebSocket и SSE

### 7.1 Клиент → сервер: отправка задачи (WebSocket)

```python
# backend/src/api/routes/websocket.py:76,127-130
ws_message = WebSocketMessage(**data)   # Pydantic-валидация

if ws_message.type == "task":
    async for event_data in ws_orchestrator.process_task(ws_message.task):
        await connection_manager.broadcast_to_conversation(event_data, event_conv_id)
```

### 7.2 SSE-эндпоинт (REST fallback)

```python
# backend/src/api/routes/tasks.py:37-43,110-118
async def event_generator(task: TaskRequest, session_id: str):
    async for event_data in orchestrator.process_task(task):
        event_json = json.dumps(event_data)
        yield f"data: {event_json}\n\n"
        await asyncio.sleep(0.01)

return EventSourceResponse(
    event_generator(task, session_id),
    media_type="text/event-stream",
    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
)
```

### 7.3 curl-пример (можно выполнить при запущенном backend)

```bash
curl -N -X POST http://localhost:8000/api/task/stream \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Сравни подходы к multi-agent orchestration",
    "enableCollaboration": true,
    "maxSubAgents": 3
  }'
# Ответ — поток SSE-событий: init → agent_status → delegation →
# agent_message_chunk × N → stream (токены финального ответа) → complete
```

---

## 8. Frontend: потребление AI-потока

Отправка задачи через WebSocket (`frontend/src/services/websocket.ts:201-211`):

```typescript
sendTask(task: TaskRequest): void {
  this.send({
    type: 'task',
    task,   // { message, conversationId?, maxSubAgents, enableCollaboration }
  });
}
```

Чтение SSE-потока через Fetch API + ReadableStream (`frontend/src/services/api.ts:54-75`):

```typescript
const reader = response.body?.getReader();
const decoder = new TextDecoder();
let buffer = '';

while (true) {
  const { done, value } = await reader.read();
  if (done) break;

  buffer += decoder.decode(value, { stream: true });
  const lines = buffer.split('\n\n');
  buffer = lines.pop() || '';

  for (const line of lines) {
    if (line.startsWith('data: ')) {
      const event: StreamEvent = JSON.parse(line.slice(6));
      yield event;   // → store.handleStreamEvent(event)
    }
  }
}
```

Event sourcing — единая точка обработки всех событий стрима
(`frontend/src/store/slices/streamSlice.ts:65-75`):

```typescript
handleStreamEvent: (event: StreamEvent) => {
  switch (event.type) {
    case 'init':
      state.initConversation(event.conversationId || '');
      state.setProcessing(true);
      set({ isStreaming: true });
      break;
    case 'agent_status':   // обновить карточку агента
    case 'stream':         // дописать токен в сообщение
    case 'complete':       // завершить, сохранить в историю
    // ... 15+ типов событий
  }
}
```

---

## 9. Трекинг токенов: callback LangChain

```python
# backend/src/infrastructure/tracking/callback_handler.py:83-114
async def on_llm_end(self, response: LLMResult, *, run_id: UUID, **kwargs):
    usage_data = self._extract_usage_from_response(response)  # OpenAI/Anthropic/Google

    if usage_data:
        token_usage = TokenUsage(
            model_id=usage_data["model_id"],
            input_tokens=usage_data["input_tokens"],
            output_tokens=usage_data["output_tokens"],
            total_tokens=usage_data["total_tokens"],
            agent_id=self.agent_id,
            request_id=str(run_id)
        )
        if self.on_usage_callback:
            await self.on_usage_callback(token_usage)  # → TokenTrackingManager.record_usage()
```

Расчёт стоимости (`backend/src/core/token_models.py:137-143`):

```python
@property
def cost(self) -> float:
    pricing = MODEL_PRICING_CONFIG.get(self.model_id)
    if not pricing:
        return 0.0
    return pricing.calculate_cost(self.input_tokens, self.output_tokens)
```

---

## 10. Embeddings (векторный поиск по диалогам)

OpenAI embeddings + pgvector (`backend/src/infrastructure/database/vector_service.py:30-47`):

```python
from openai import AsyncOpenAI

self.client = AsyncOpenAI(api_key=openai_api_key or settings.openai_api_key)

response = await self.client.embeddings.create(
    model=self.model,            # "text-embedding-3-small"
    input=text,
    encoding_format="float"
)
return response.data[0].embedding   # List[float], размерность 1536
```
