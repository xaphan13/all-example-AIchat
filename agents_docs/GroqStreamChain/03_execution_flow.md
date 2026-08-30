# 03 — Логика и работа кода (Execution Flow)

## Жизненный цикл приложения

### 1. Инициализация (при импорте `server.py`)

```
config.py:  load_dotenv()  →  GROQ_API_KEY, MODEL_NAME, LLM_CONFIG, HOST, PORT загружены
server.py:  app = FastAPI()
            app.mount("/static", ...)           ← статические файлы
            templates = Jinja2Templates(...)     ← HTML-шаблоны
            llm_service = LLMService()           ← создаёт Groq-клиент и ChatGroq
            chat_sessions = {}                   ← пустое in-memory хранилище
            active_connections = {}              ← мёртвая переменная (не используется)
            manager = ConnectionManager()        ← реестр WebSocket-соединений
```

**Важно:** `LLMService.__init__` (`services/llm_service.py:16-23`) создаёт **два** клиента:
- `self.client = Groq(api_key=GROQ_API_KEY)` — используется для стриминга.
- `self.langchain_client = ChatGroq(...)` — **создаётся, но никогда не вызывается**. Мёртвый код, расходует память и время инициализации.

### 2. Запуск

```python
# server.py:148-149
if __name__ == "__main__":
    uvicorn.run("server:app", host=HOST, port=PORT, reload=True)
```

- Uvicorn запускает ASGI-сервер на `0.0.0.0:8000` с `reload=True` (hot-reload при изменении файлов).
- `reload=True` **не должен использоваться в production** — вызывает overhead от file-watcher и потенциальные race conditions.

### 3. Завершение работы

- **Graceful shutdown отсутствует.** Нет обработчиков `SIGTERM`/`SIGINT` для корректного закрытия WebSocket-соединений или сохранения состояния сессий.
- При остановке процесса все in-memory сессии и активные WebSocket-соединения обрываются без уведомления клиентов.
- `ConnectionManager` не имеет метода `close_all()` или аналога.

---

## Ключевые бизнес-процессы

### Процесс 1: Установка WebSocket-соединения и инициализация сессии

**Файл:** `server.py:65-83` (`websocket_endpoint`)

```
Шаг 1:  Клиент открывает WebSocket → ws://host:8000/ws/chat
Шаг 2:  manager.connect(websocket)
          → websocket.accept()
          → session_id = uuid.uuid4()
          → active_connections[session_id] = websocket
          → chat_sessions[session_id] = ChatSession(id=session_id)
Шаг 3:  Отправка {"type": "session_id", "session_id": session_id}
Шаг 4:  Создание welcome-сообщения "Hello! I'm your AI assistant..."
          → chat_sessions[session_id].messages.append(Message(role="assistant", ...))
          → отправка {"type": "initial_message", "content": welcome_message}
Шаг 5:  Вход в бесконечный цикл ожидания сообщений (while True)
```

### Процесс 2: Обработка пользовательского сообщения и стриминг ответа

**Файлы:** `server.py:85-131` (цикл), `services/llm_service.py:52-95` (стриминг)

```
Шаг 1:  data = await websocket.receive_text()
Шаг 2:  json.loads(data) → user_message = data["message"]
Шаг 3:  chat_sessions[session_id].messages.append(Message(role="user", content=user_message))
Шаг 4:  Отправка ACK: {"type": "message_received", "status": "processing"}
Шаг 5:  Вызов llm_service.generate_response_stream(chat_sessions[session_id].messages):
          5a: messages.insert(0, {"role": "system", "content": SYSTEM_PROMPT})
              ⚠ МУТАЦИЯ: системный промпт добавляется в начало списка сообщений сессии
              при КАЖДОМ вызове. Список растёт на 1 системное сообщение каждый ход.
          5b: _convert_to_groq_messages(messages) → список dict'ов
          5c: asyncio.to_thread(client.chat.completions.create, stream=True)
              ← Синхронный Groq-вызол обёрнут в to_thread для неблокируемости
          5d: for chunk in completion:
                content = chunk.choices[0].delta.content
                yield content
Шаг 6:  Для каждого чанка (server.py:107-113):
          → websocket.send_json({"type": "stream", "content": response_chunk})
          → full_response += response_chunk
Шаг 7:  После завершения стрима:
          → chat_sessions[session_id].messages.append(Message(role="assistant", content=full_response))
          → websocket.send_json({"type": "stream_end", "session_id": session_id})
Шаг 8:  Возврат к шагу 1 (ожидание следующего сообщения)
```

### Процесс 3: Отключение клиента

**Файл:** `server.py:133-140`

```
Шаг 1:  WebSocketDisconnect (исключение из websocket.receive_text())
Шаг 2:  if 'session_id' in locals():
          manager.disconnect(session_id)
            → del active_connections[session_id]
Шаг 3:  ⚠ chat_sessions[session_id] НЕ удаляется — сессия остаётся в памяти навсегда (memory leak)
```

---

## Роутинг и Middleware

### HTTP-роуты

| Метод | Путь | Обработчик | Назначение |
|---|---|---|---|
| `GET` | `/` | `server.py:39-41` — `get_index()` | Возвращает `templates/index.html` через Jinja2Templates. |
| `GET` | `/health` | `server.py:143-145` — `health_check()` | Health-check: `{"status": "ok"}`. |
| WebSocket | `/ws/chat` | `server.py:65-140` — `websocket_endpoint()` | Основной чат-эндпоинт. |

### Middleware

**Middleware отсутствует.** Нет:
- CORS middleware (приложение не отдаёт CORS-заголовки).
- Аутентификации / авторизации.
- Rate limiting.
- Request logging middleware.
- Compression middleware.

### Static files

`server.py:24` — `app.mount("/static", StaticFiles(directory="static"))` — отдаёт CSS, JS, изображения напрямую.

---

## Механизмы обработки ошибок

### Серверная сторона (`server.py`)

| Уровень | Обработка | Оценка |
|---|---|---|
| WebSocket-отключение | `except WebSocketDisconnect` → `manager.disconnect()` | Корректно, но не очищает `chat_sessions`. |
| Ошибка LLM-вызова | `except Exception` внутри цикла → `send_json({"type": "error", ...})` | Пользователь получает уведомление, цикл продолжается. |
| Прочие WebSocket-ошибки | `except Exception` → лог + `disconnect()` | Общий catch-all, цикл прерывается. |
| Отсутствие `GROQ_API_KEY` | Не обрабатывается при старте | Падение при первом вызове Groq с `None` key. |

### LLM-сервис (`services/llm_service.py`)

```python
except Exception as e:
    logger.error(f"Error in LLM service: {e}", exc_info=True)
    yield "I'm sorry, I encountered an error processing your request."
```
- Все исключения перехватываются broad `except Exception`.
- Ошибка возвращается как **обычный текстовый чанк** через `yield`, что означает: клиент получит её как часть ответа ассистента, а не как ошибку. Это нарушает контракт стриминга.

### Клиентская сторона (`static/js/main.js`)

| Событие | Обработка |
|---|---|
| `socket.onclose` | Exponential backoff reconnect: до 5 попыток, задержка `min(1000 * 2^attempts, 10000)` ms. |
| `socket.onerror` | `console.error` — без recovery-логики. |
| Ошибка парсинга JSON | `try/catch` вокруг `JSON.parse` → `console.error`. |
| Ошибка отправки | `try/catch` вокруг `socket.send` → отображение ошибки в UI. |
| `type: "error"` | Удаление typing-indicator, отображение красного сообщения. |

---

## Логирование

**Конфигурация:** `server.py:18` — `logging.basicConfig(level=logging.INFO)`

| Модуль | Уровень | Что логируется |
|---|---|---|
| `server.py` | `INFO` | Подключения, отключения, получение сообщений, отправка ACK, старт/конец стрима. |
| `server.py` | `DEBUG` | Чанки стрима (`response_chunk[:20]`) — но `DEBUG` не включён в `basicConfig`. |
| `services/llm_service.py` | `INFO` | Подготовка запроса, отправка в Groq, получение ответа, завершение стрима. |
| `services/llm_service.py` | `ERROR` | Исключения с `exc_info=True`. |

**Недостатки логирования:**
- Нет structured logging (JSON-формат).
- Нет correlation/request ID для трассировки.
- Нет ротации логов.
- `f-strings` в логгере вычисляются всегда, даже если уровень отключён (не используется `logger.info("...", arg)` pattern).
- Логируется `data[:50]` — обрезка может маскировать проблемы при коротких payload'ах.
