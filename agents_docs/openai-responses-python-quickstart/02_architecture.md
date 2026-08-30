# 02. Архитектура и паттерны (Architecture & Patterns)

## 1. Высокоуровневая архитектура

**Тип: монолит с серверным рендерингом (server-rendered monolith)**, развёрнутый как единый FastAPI-процесс (`main.py`). Классическая слоистая организация внутри одного приложения:

```
┌─────────────────────────── Браузер ───────────────────────────┐
│  HTMX + sse.js + stream-md.js + marked + DOMPurify            │
└──────────────┬──────────────────────────────┬─────────────────┘
               │ POST /chat/{id}/send         │ SSE GET /chat/{id}/receive
               │ (HTML-фрагменты)             │ (EventSource)
┌──────────────▼──────────────────────────────▼─────────────────┐
│ HTTP/Web-слой: routers/ (chat, files, setup, audio)           │
│   — обработка форм, рендер Jinja2, StreamingResponse(SSE)    │
├────────────────────────────────────────────────────────────────┤
│ Сервисный слой: utils/                                         │
│   — config (env/.json), function_calling (реестр инструментов),│
│   — computer_use (Playwright-сессии), files (vector store),   │
│   — sse, conversations, tool_tasks                             │
├────────────────────────────────────────────────────────────────┤
│ Внешние границы: OpenAI SDK (AsyncOpenAI) · Playwright · MCP   │
└────────────────────────────────────────────────────────────────┘
```

Слойность выражена неявно: `routers/*` — единственный потребитель FastAPI; `utils/*` не импортируют `routers` (кроме `routers/chat.py`, который использует `routers/files.router` только для генерации URL через `url_path_for` — зависимость на уровне маршрутизации, не бизнес-логики). Единая точка входа — `app` в `main.py`; зависимость инверсии — через `Depends(...)`.

## 2. Ключевые архитектурные решения

1. **Стриминг через SSE как транспорт чата.** Ответ OpenAI (`responses.create(stream=True)`) перекодируется из потока событий `ResponseStreamEvent` в поток SSE-событий для HTMX. Разные типы событий обрабатываются по-разному: `textDelta` → накопительный Markdown-рендер на клиенте, `toolDelta` → live-поток аргументов tool-вызова, `messageCreated` → HTMX-своп фрагмента.
2. **Состояние разговора хранится на стороне OpenAI**, сервер лишь передаёт `conversation_id` из URL (см. `utils/conversations.py` и маршрут `/chat/{conversation_id}/...`). Сервер не ведёт собственную историю.
3. **Конфигурация ассистента — локальная**: `.env` (модель, инструкции, `ENABLED_TOOLS`, параметры web_search/image_generation) и `tool.config.json` (реестр кастомных функций и MCP-серверов). OpenAI не хранит конфигурацию — это принципиальное отличие от Assistants API, отмеченное в `README.md`.
4. **«Рестарт потока» (run loop):** после `ResponseCompletedEvent` с tool-вызовами сервер выполняет их, записывает результаты в conversation и **пересоздаёт `responses.create`** (рекурсия `iterate_stream`). Если есть `McpApprovalRequest` — рестарт не выполняется, продолжение инициирует пользователь через `POST /approve`.

## 3. Паттерны проектирования

| Паттерн | Где реализован | Назначение |
|---|---|---|
| **Registry** | `ToolRegistry` (`utils/function_calling.py`) | Регистрация функций по имени, `get_tool_def_list()` для генерации tool-дефиниций, диспетчеризация `call(name, args)` |
| **Dependency Injection** | `Depends(lambda: AsyncOpenAI())` во всех роутерах | Инжекция клиента OpenAI; легко подменяется в тестах (`patch("routers.chat.AsyncOpenAI")`) |
| **Protocol / Strategy (интерфейс + подменяемая реализация)** | `ComputerSession`, `ComputerSessionManager` (`@runtime_checkable`) в `utils/computer_use.py` | Позволяет заменить Playwright-бэкенд на VNC/xdotool/pyautogui без изменения `routers/chat.py` |
| **Singleton (модульный)** | `session_manager = BrowserSessionManager()` | Единственный менеджер Playwright-сессий на весь процесс |
| **Factory** | `func_metadata()` → `create_model()` | Динамическое создание Pydantic-моделей аргументов из сигнатуры функции |
| **Adapter** | `BrowserSession` (адаптирует Playwright-API к протоколу `ComputerSession`) | Единый интерфейс `screenshot/execute/close` |
| **Generic Result Object** | `FunctionResult[T]` (`error` / `warning` / `result`) | Единый контракт возврата tool-вызовов для шаблонов |
| **Template Method (state-machine)** | `iterate_stream()` в `routers/chat.py` (`match event:`) | Обработка ~20 типов событий Responses API по единому алгоритму |
| **Decorator** | `ToolRegistry.tool()` | Альтернативный способ регистрации функций |
| **OOB (Out-of-Band) swap** | `wrap_for_oob_swap()` + `hx-swap-oob="beforeend:#step-{id}"` | Инкрементальная доставка дельт текста/инструментов в DOM |

## 4. Поток данных (Data Flow)

### 4.1 Отправка сообщения (не-стриминговый этап)

```
Пользователь → form#chatForm (multipart, images[] + userInput)
  → POST /chat/{conversation_id}/send        (routers/chat.py:send_message)
  → для каждого image: client.files.create(purpose="vision")  [OpenAI Files API]
  → client.conversations.items.create(type="message", role="user")
  → HTMLResponse = user-message.html + assistant-run.html
```

`assistant-run.html` содержит `sse-connect="{{ url_for('stream_response', ...) }}"` — после вставки фрагмента HTMX-расширение `sse.js` автоматически открывает `EventSource`.

### 4.2 Стриминг ответа (SSE, основной конвейер)

```
GET /chat/{id}/receive
  → event_generator()
    1. load_dotenv; чтение RESPONSES_MODEL / RESPONSES_INSTRUCTIONS / ENABLED_TOOLS
    2. сборка tools[] из ENABLED_TOOLS + tool.config.json (+ WEB_SEARCH_*, IMAGE_GENERATION_*)
    3. client.responses.create(conversation, model, tools, instructions, stream=True)
    4. iterate_stream(stream):
       ResponseCreatedEvent           → сохранить response_id
       OutputItemAdded (message)      → SSE "messageCreated" (новый шаг)
       TextDelta / RefusalDelta       → SSE "textDelta" (OOB-аппенд в шаг)
       FunctionCallArgumentsDelta     → SSE "toolDelta" (поток аргументов, если SHOW_TOOL_CALL_DETAIL)
       OutputItemDone (function_call) → создание asyncio.Task на выполнение функции
       OutputItemDone (computer_call)→ coroutine на execute_computer_actions (sequential)
       OutputItemDone (image_gen)     → SSE "imageOutput" (base64 PNG)
       OutputItemDone (code_interp)   → список container-файлов → SSE "fileOutput" (карусель)
       Annotation (file_citation /
                    container_file_citation / url_citation)
                                      → SSE "textDelta"/"textReplacement"/"imageOutput"
       McpApprovalRequest             → SSE "mcpApprovalRequest" + коммит item в conversation
       ResponseCompleted:
         есть tool-задачи → asyncio.gather (functions параллельно, computer последовательно)
                           → conversations.items.create для каждого output по отдельности
                           → рестарт responses.create (однократно) → рекурсивный iterate_stream
         approval-запрос  → завершить поток без рестарта
         нет задач        → SSE "runCompleted" + "endStream"
  → StreamingResponse(media_type="text/event-stream")
```

На клиенте `stream-md.js`:
- `textDelta` → аккумулируется в `WeakMap` по целевому элементу, рендерится `marked.parse()` + `DOMPurify.sanitize()` с последующим автоскроллом.
- `toolDelta` → либо заменяет содержимое (data-tool-delta="replace"), либо накапливает в `<pre data-tool-delta="stream">`.
- `textReplacement` → regex-замена `sandbox:/path` на URL скачивания.
- `endStream` → закрытие EventSource (атрибут `sse-close="endStream"`), re-enable кнопки Send.

### 4.3 MCP approval flow

```
SSE "mcpApprovalRequest" → UI-карточка (mcp-approval-request.html)
  → POST /chat/{id}/approve  (routers/chat.py:approve_mcp_tool)
  → conversations.items.create(type="mcp_approval_response", approve, reason)
  → HTMLResponse = acknowledgement + новый assistant-run (новый SSE-цикл)
```

### 4.4 Файлы

```
POST /files (upload) → validate → files.create + vector_stores.files.create (параллельно через gather)
                     → store_file() локально в uploads/ → повторный список → merge (eventual consistency)
GET  /files/{file_name}          → retrieve_file() (FileResponse из uploads/)
GET  /files/{container_id}/{file_id}/openai_content → Containers API + files.content (stream)
GET  /files/{file_id}/content    → files.content (для миниатюр vision-изображений)
DELETE /files/{file_id} и /files → vector store + OpenAI file + локальная копия
```

## 5. Состояние, кэширование, конфигурация

| Слой состояния | Хранение | Чтение/запись | Кэширование |
|---|---|---|---|
| Конфигурация ассистента | `.env` (плоские пары) | `utils/config.py:update_env_file()`, `load_dotenv` | нет; перечитывается на каждый запрос (намеренно, чтобы GUI-изменения вступали в силу без рестарта) |
| Реестр инструментов | `tool.config.json` (JSON) | `read_registry_entries()`, `read_mcp_servers()`, `generate_registry_file()` | нет; в `stream_response` читается через `asyncio.to_thread` |
| Conversation state | OpenAI (server-side) | `conversations.items.create` / `conversations.create` | нет |
| Файлы | OpenAI (files/vector store) + локальная копия в `uploads/` | `utils/files.py` | `VECTOR_STORE_ID` кэшируется в `.env` |
| Browser-сессии (computer use) | in-memory `dict[conversation_id, BrowserSession]` | `session_manager` | Кэш сессий; `close_all()` на shutdown, иначе живут вечно |
| Кэш-серверы (Redis и т.п.) | — | — | отсутствуют |

**Особенности конфигурирования:**
- Переменные окружения (`OPENAI_API_KEY`, `RESPONSES_MODEL`, `RESPONSES_INSTRUCTIONS`, `ENABLED_TOOLS`, `SHOW_TOOL_CALL_DETAIL`, `VECTOR_STORE_ID`, `WEB_SEARCH_*`, `IMAGE_GENERATION_*`, `COMPUTER_USE_DISPLAY_WIDTH/HEIGHT`) читаются в теле роутеров через `load_dotenv(override=True)`, поэтому правки через `/setup` применяются мгновенно.
- `update_env_file` производит перезапись файла строками (`r`+`\n`-нормализация) — не потокобезопасен при конкурентных записях.
- `get_or_create_vector_store` создаёт store один раз и пишет id в `.env`.

## 6. Конкурентность и асинхронность

- Всё I/O — async (`AsyncOpenAI`, Playwright async API). Единственный блокирующий вызов в горячем пути вынесен в `asyncio.to_thread` (`tool.config.json`).
- Параллельные tool-вызовы: `asyncio.gather(..., return_exceptions=True)` для function-задач; computer-вызовы выполняются **последовательно** (закомментированное обоснование: гонки в браузере).
- При `asyncio.CancelledError` (разрыв SSE) задачи отменяются через `task.cancel()` + `gather`.
- Узкое место конкурентности: `download_container_file` (routers/files.py:366-368) мутирует общий `client.base_url` — при параллельных запросах к разным container_id возможна гонка.
