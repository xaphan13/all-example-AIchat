# 02 — Архитектура и паттерны

## Высокоуровневая архитектура

Проект построен как **монолитное single-process ASGI-приложение** на FastAPI. Все компоненты (HTTP-роутинг, WebSocket-обработка, LLM-вызовы, хранение состояния) находятся в одном процессе без межсервисного взаимодействия.

```
┌─────────────────────────────────────────────────────┐
│                     Browser (Client)                  │
│  templates/index.html + static/js/main.js + style.css │
└──────────────────────┬──────────────────────────────┘
                       │ WebSocket (ws://host:8000/ws/chat)
                       │ HTTP GET / (HTML), GET /health
┌──────────────────────▼──────────────────────────────┐
│                  FastAPI (server.py)                   │
│                                                        │
│  ┌─────────────┐  ┌──────────────────┐                │
│  │ HTTP Routes  │  │ ConnectionManager │                │
│  │ / → HTML     │  │ (WebSocket pool)  │                │
│  │ /health      │  │                  │                │
│  └─────────────┘  └────────┬─────────┘                │
│                             │                          │
│              ┌──────────────▼──────────────┐           │
│              │  In-memory state (dict)      │           │
│              │  chat_sessions: {id: ChatSession} │     │
│              │  active_connections: {id: WS}   │       │
│              └──────────────┬──────────────┘           │
│                             │                          │
│              ┌──────────────▼──────────────┐           │
│              │  LLMService (services/)      │           │
│              │  Groq SDK (streaming)        │           │
│              │  ChatGroq (init, unused)     │           │
│              └──────────────┬──────────────┘           │
└─────────────────────────────┼─────────────────────────┘
                              │ HTTPS (asyncio.to_thread)
                   ┌──────────▼──────────┐
                   │  Groq Cloud API      │
                   │  (api.groq.com)      │
                   └─────────────────────┘
```

### Слои

1. **Presentation Layer (Frontend):** `templates/index.html` + `static/js/main.js` — рендеринг UI, управление WebSocket-соединением, обработка стрим-чанков.
2. **Transport Layer:** `server.py` — FastAPI HTTP + WebSocket, `ConnectionManager` для управления соединениями.
3. **Business Logic Layer:** `services/llm_service.py` — инкапсуляция вызова LLM, конвертация форматов сообщений, стриминг.
4. **Data Layer:** `models/chat.py` — Pydantic-модели; хранилище — in-memory dict (без отдельного data-access слоя).

---

## Основные паттерны проектирования

| Паттерн | Где применяется | Описание |
|---|---|---|
| **Singleton (де-факто)** | `server.py:30` — `llm_service = LLMService()` | Единственный экземпляр `LLMService` создаётся на уровне модуля и разделяется между всеми WebSocket-соединениями. |
| **Manager / Registry** | `server.py:44-61` — `ConnectionManager` | Централизованно хранит активные WebSocket-соединения в dict, предоставляет `connect()`/`disconnect()`. |
| **Service Layer** | `services/llm_service.py` — `LLMService` | Изоляция логики взаимодействия с LLM от транспортного слоя. |
| **DTO / Data Transfer Object** | `models/chat.py` — `Message`, `ChatSession`, `ChatRequest` | Pydantic-модели для передачи данных между слоями. |
| **Adapter** | `services/llm_service.py:25-50` — `_convert_to_langchain_messages()`, `_convert_to_groq_messages()` | Адаптация доменных моделей `Message` к форматам LangChain и Groq. |
| **Async Generator (Streaming)** | `services/llm_service.py:52-95` — `generate_response_stream()` | `AsyncGenerator[str, None]` для поэтапной выдачи чанков ответа LLM. |

### Паттерны, которые **отсутствуют**, но ожидаемы

- **Dependency Injection:** зависимости (`LLMService`, `ConnectionManager`) создаются статически на уровне модуля, нет контейнера DI или фабрик.
- **Repository Pattern:** нет абстракции над хранилищем; `chat_sessions` dict напрямую мутируется в `server.py`.
- **Factory Pattern:** нет фабрик для создания сессий или сообщений (всё inline).

---

## Схема потока данных (Data Flow)

### Полный цикл WebSocket-сообщения

```
1. Client (main.js)
   │  new WebSocket("ws://host:8000/ws/chat")
   ▼
2. server.py: websocket_endpoint()
   │  manager.connect(websocket)
   │    → websocket.accept()
   │    → session_id = uuid4()
   │    → active_connections[session_id] = websocket
   │    → chat_sessions[session_id] = ChatSession(id=session_id)
   │  → send {"type": "session_id", "session_id": ...}
   │  → send {"type": "initial_message", "content": "Hello!..."}
   ▼
3. Client (main.js)
   │  socket.onmessage → handleSocketMessage()
   │    → сохраняет sessionId в localStorage
   │    → рендерит welcome-сообщение
   ▼
4. Client (main.js)
   │  sendMessage() → socket.send(JSON.stringify({message: "..."}))
   ▼
5. server.py: websocket_endpoint() — цикл while True
   │  data = await websocket.receive_text()
   │  → json.loads(data) → user_message
   │  → chat_sessions[session_id].messages.append(Message(role="user", ...))
   │  → send {"type": "message_received", "status": "processing"}
   ▼
6. services/llm_service.py: generate_response_stream()
   │  → messages.insert(0, system_message)     ← МУТАЦИЯ исходного списка!
   │  → _convert_to_groq_messages(messages)
   │  → asyncio.to_thread(client.chat.completions.create, stream=True)
   │  → for chunk in completion:
   │      yield chunk.choices[0].delta.content
   ▼
7. server.py: websocket_endpoint() — async for
   │  → send {"type": "stream", "content": chunk}  (для каждого чанка)
   │  → full_response += chunk
   │  → после завершения: chat_sessions[session_id].messages.append(Message(role="assistant", ...))
   │  → send {"type": "stream_end", "session_id": ...}
   ▼
8. Client (main.js)
   │  handleSocketMessage() → case "stream": appendToAssistantMessage(content)
   │  → case "stream_end": isProcessing = false, enableUserInput()
```

---

## Управление состоянием

### Хранение сессий

- **In-memory dict** `chat_sessions: Dict[str, ChatSession]` (`server.py:33`) — создаётся при подключении, накапливает сообщения, **не персистится**. При рестарте сервера все сессии теряются.
- **In-memory dict** `active_connections: Dict[str, WebSocket]` (`server.py:36`) — дублирует `ConnectionManager.active_connections` (`server.py:46`). Модульная переменная `active_connections` **никогда не используется** — это мёртвый код.

### Управление конфигурацией

| Параметр | Источник | Значение по умолчанию |
|---|---|---|
| `GROQ_API_KEY` | `.env` → `os.getenv()` | `None` (обязателен) |
| `MODEL_NAME` | `.env` → `os.getenv()` | `None` (обязателен) |
| `LLM_CONFIG.temperature` | `config.py:13` | `0.0` |
| `LLM_CONFIG.max_tokens` | `config.py:14` | `512` |
| `LLM_CONFIG.top_p` | `config.py:15` | `1` |
| `LLM_CONFIG.stream` | `config.py:16` | `True` |
| `HOST` | `config.py:21` | `"0.0.0.0"` |
| `PORT` | `config.py:22` | `8000` |

### Кэширование

Кэширование **отсутствует** на всех уровнях. Каждый запрос к LLM — полный round-trip к Groq API без кэширования промптов или ответов.

### Обработка конфигурации — уязвимости

- `GROQ_API_KEY` и `MODEL_NAME` не имеют fallback-значений и не валидируются при старте. Если `.env` отсутствует, приложение запустится, но упадёт при первом LLM-вызове с `None`-ключом.
- Нет файла `.env.example` для документации обязательных переменных.
- `pyproject.toml` декларирует `requires-python >=3.13`, но `README.md` указывает Python 3.9. `.python-version` — `3.13`. Конфликт метаданных.
