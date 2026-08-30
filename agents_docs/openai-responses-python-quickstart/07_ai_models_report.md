# 07. Отчёт по работе приложения с моделями AI

## Содержание

1. [Обзор приложения и его возможностей](#1-обзор-приложения-и-его-возможностей)
2. [Модели и провайдеры](#2-модели-и-провайдеры)
3. [Формат общения с нейросетями](#3-формат-общения-с-нейросетями)
4. [Примеры кода, работающего с AI](#4-примеры-кода-работающего-с-ai)
5. [Мультиагентное использование](#5-мультиагентное-использование)
6. [Архитектура взаимодействия с AI](#6-архитектура-взаимодействия-с-ai)
7. [Ограничения и нюансы](#7-ограничения-и-нюансы)

---

## 1. Обзор приложения и его возможностей

`openai-responses-python-quickstart` — монолитное чат-приложение, построенное поверх
**OpenAI Responses API** (`/v1/responses`). Технологический стек: Python 3.13 + FastAPI
+ Jinja2 + HTMX. Сервер выступает тонким посредником (proxy/orchestrator) между
браузером и OpenAI API.

### Ключевые возможности

| Возможность | Описание |
|---|---|
| **Потоковый чат (SSE)** | Ответы модели стримятся в реальном времени через Server-Sent Events с инкрементальным рендерингом Markdown на клиенте (`stream-md.js` + `marked` + `DOMPurify`) |
| **Мультимодальный ввод** | Поддержка отправки изображений вместе с текстом (vision): файлы загружаются через OpenAI Files API с `purpose="vision"` |
| **Голосовой ввод** | Запись аудио в браузере (`audio-recorder.js` → MediaRecorder) и транскрибация через Whisper (`POST /audio/transcribe`) |
| **Семь типов инструментов** | Code interpreter, file search, custom functions, MCP, web search, computer use, image generation |
| **Управление файлами** | Загрузка, хранение (Vector Store + локальная копия в `uploads/`), удаление, просмотр файлов |
| **Computer use** | Модель может управлять headless-браузером Playwright: клики, ввод текста, скроллинг, скриншоты |
| **Локальная конфигурация** | Модель, инструкции, набор инструментов настраиваются через веб-UI `/setup` и хранятся в `.env` + `tool.config.json` — без перезапуска сервера |
| **MCP-интеграция** | Подключение внешних MCP-серверов с поддержкой approval-флоу (одобрение вызова инструмента пользователем) |
| **Сохранение состояния диалога** | История разговора хранится на стороне OpenAI (Conversation API); сервер передаёт только `conversation_id` |

---

## 2. Модели и провайдеры

### 2.1 Единственный провайдер — OpenAI

Приложение работает **исключительно с OpenAI API**. Все вызовы идут через официальный
Python SDK `openai>=2.0.0` (класс `AsyncOpenAI`). Поддержка других провайдеров
(Anthropic, Google, локальные модели) в шаблоне **не реализована**.

Ключевые эндпоинты OpenAI, используемые приложением:

| API | Назначение | Где используется |
|---|---|---|
| `responses.create` | Генерация ответов модели (стриминг) | `routers/chat.py` |
| `conversations.create` / `conversations.items.create` | Управление состоянием диалога | `utils/conversations.py`, `routers/chat.py` |
| `files.create` / `files.content` / `files.delete` | Загрузка изображений (vision), скачивание контента | `routers/chat.py`, `routers/files.py` |
| `vector_stores.files.create` / `.list` / `.delete` | Vector Store для file search | `utils/files.py`, `routers/files.py` |
| `containers.files.list` / `containers.files.retrieve` | Песочница code interpreter | `routers/chat.py`, `routers/files.py` |
| `audio.transcriptions.create` | Транскрибация аудио (Whisper) | `routers/audio.py` |

### 2.2 Список доступных моделей

Список моделей захардкожен в `routers/setup.py` (не запрашивается у API динамически).
Пользователь выбирает модель на странице `/setup`:

```python
available_models: list[str] = sorted([
    "gpt-4.1", "gpt-4.1-mini", "gpt-4.1-nano",
    "gpt-4o", "gpt-4o-mini", "o1", "o1-mini",
    "o3", "o3-pro", "o3-mini", "o4-mini",
    "o3-deep-research", "o4-mini-deep-research",
    "gpt-5", "gpt-5.4", "gpt-5-mini", "gpt-5-nano",
    "gpt-oss-120b", "gpt-oss-20b"
])
```

Выбранная модель сохраняется в `.env` как `RESPONSES_MODEL` и используется при каждом
вызове `responses.create`. Модель по умолчанию (если не задана) — `gpt-5-mini`.

### 2.3 Модель для транскрибации аудио

Для голосового ввода используется модель **Whisper** (`whisper-1`), захардкоженная в
`routers/audio.py`:

```python
transcription = await client.audio.transcriptions.create(
    model="whisper-1",
    file=(audio.filename, await audio.read(), audio.content_type),
)
```

### 2.4 Можно ли использовать другие провайдеры?

Напрямую — нет. Однако архитектура предусматривает точки расширения:

1. **Computer use** абстрагирован через протоколы `ComputerSession` /
   `ComputerSessionManager` — можно заменить Playwright на любой другой бэкенд (VNC,
   xdotool, pyautogui) без изменения `routers/chat.py`.
2. **Custom functions** — произвольные Python-функции, регистрируемые через
   `tool.config.json`. Они не зависят от OpenAI и могут вызывать любые внешние API.
3. **MCP-серверы** — позволяют подключать сторонние инструменты по стандарту MCP, что
   расширяет возможности модели без изменения кода приложения.

Для подключения не-OpenAI моделей потребуется замена `AsyncOpenAI` на соответствующий
клиент и адаптация `iterate_stream()` под формат событий другого провайдера.

---

## 3. Формат общения с нейросетями

### 3.1 Транспорт: SSE (Server-Sent Events)

Общение между браузером и сервером происходит через **SSE**. Клиент открывает
`EventSource` на `GET /chat/{conversation_id}/receive`, и сервер потоково отправляет
события:

```
event: textDelta
data: <span hx-swap-oob="beforeend:#step-abc123">Привет</span>

event: toolCallCreated
data: <div id="step-def456">Calling get_weather tool...</div>

event: runCompleted
data: <span hx-swap-oob="outerHTML:.dots"></span>

event: endStream
data: DONE
```

Форматирование SSE-сообщений выполняет утилита `utils/sse.py`:

```python
def sse_format(event: str, data: str, retry: int | None = None) -> str:
    output = f"event: {event}\n"
    if retry is not None:
        output += f"retry: {retry}\n"
    for line in data.splitlines():
        output += f"data: {line}\n"
    output += "\n"
    return output
```

### 3.2 Типы SSE-событий

| Событие | Назначение |
|---|---|
| `messageCreated` | Новый шаг-сообщение ассистента (HTMX-своп фрагмента) |
| `textDelta` | Инкрементальная дельта текста (накопительный Markdown-рендер) |
| `toolCallCreated` | Начало вызова инструмента (новый шаг в UI) |
| `toolDelta` | Поток аргументов tool-вызова / кода code interpreter |
| `toolOutput` | Результат выполнения инструмента (HTML-фрагмент) |
| `imageOutput` | Изображение (base64 PNG) — computer use, image generation, code interpreter |
| `fileOutput` | Карусель файлов из code interpreter |
| `textReplacement` | Замена `sandbox:/path` на URL скачивания файла |
| `mcpApprovalRequest` | Карточка одобрения MCP-вызова (Approve/Reject) |
| `runCompleted` | Завершение генерации (очистка индикатора загрузки) |
| `networkError` | Сетевая ошибка |
| `endStream` | Закрытие EventSource на клиенте (`DONE` или `ERROR`) |

### 3.3 Формат сообщений на стороне OpenAI

Пользовательские сообщения отправляются в OpenAI Conversations API:

```python
await client.conversations.items.create(
    conversation_id=conversation_id,
    items=[{
        "type": "message",
        "role": "user",
        "content": [
            {"type": "input_text", "text": f"System: Today's date is {date}\n{userInput}"},
            {"type": "input_image", "file_id": openai_file.id},  # если есть изображения
        ]
    }]
)
```

Ответы модели стримятся через `responses.create(stream=True)` — сервер обрабатывает
~20 типов событий Responses API в state-machine `iterate_stream()`.

### 3.4 Рендеринг на клиенте

Клиентский JavaScript (`static/stream-md.js`):
- `textDelta` → аккумулируется в `WeakMap` по целевому элементу, рендерится через
  `marked.parse()` + `DOMPurify.sanitize()` с автоскроллом;
- `toolDelta` → либо заменяет содержимое (`data-tool-delta="replace"`), либо накапливается
  в `<pre data-tool-delta="stream">`;
- `textReplacement` → regex-замена `sandbox:/path` на URL;
- `endStream` → закрытие `EventSource`, разблокировка кнопки Send.

---

## 4. Примеры кода, работающего с AI

### 4.1 Создание диалога (Conversation)

```python
# utils/conversations.py
async def create_conversation() -> str:
    """Создание диалога на стороне OpenAI и возврат его id."""
    client: AsyncOpenAI = AsyncOpenAI()
    conv = await client.conversations.create()
    return conv.id
```

### 4.2 Отправка пользовательского сообщения с изображениями

```python
# routers/chat.py — send_message (упрощённо)

# Формирование мультимодального контента
content: list[dict[str, str]] = [{
    "type": "input_text",
    "text": f"System: Today's date is {datetime.now().astimezone().strftime('%Y-%m-%d')}\n{userInput}"
}]

# Загрузка изображений в OpenAI Files API
for image in images:
    if image and image.filename and image.size:
        image_bytes = await image.read()
        openai_file = await client.files.create(
            file=(image.filename, image_bytes),
            purpose="vision"
        )
        content.append({"type": "input_image", "file_id": openai_file.id})

# Запись сообщения в диалог
await client.conversations.items.create(
    conversation_id=conversation_id,
    items=[{"type": "message", "role": "user", "content": content}]
)
```

### 4.3 Стриминг ответа модели (основной вызов)

```python
# routers/chat.py — stream_response (упрощённо)

stream = await client.responses.create(
    input="",
    conversation=conversation_id,      # состояние хранится на стороне OpenAI
    model=model,                        # из .env: RESPONSES_MODEL
    tools=tools or NOT_GIVEN,           # собранный список инструментов
    instructions=instructions,          # из .env: RESPONSES_INSTRUCTIONS
    parallel_tool_calls=True,           # параллельные tool-вызовы разрешены
    stream=True                         # потоковый режим
)

# Обработка потока событий
async for sse in iterate_stream(stream):
    yield sse
```

### 4.4 Сборка инструментов для модели

```python
# routers/chat.py — сборка tools[] (упрощённо)

tools: list[dict[str, Any]] = []

if "file_search" in enabled_tools:
    tools.append({"type": "file_search", "vector_store_ids": [vector_store_id]})

if "code_interpreter" in enabled_tools:
    tools.append({"type": "code_interpreter", "container": {"type": "auto"}})

if "function" in enabled_tools:
    # Динамическая регистрация Python-функций из tool.config.json
    for fn_config in TOOL_CONFIG.custom_functions:
        module = importlib.import_module(fn_config.import_path)
        fn = getattr(module, fn_config.name)
        FUNCTION_REGISTRY.add_function(fn, name=fn_config.name)
    tools.extend(FUNCTION_REGISTRY.get_tool_def_list())

if "mcp" in enabled_tools:
    tools.extend(TOOL_CONFIG.mcp_servers)  # тип Mcp из OpenAI SDK

if "web_search" in enabled_tools:
    tools.append({"type": "web_search_preview", "search_context_size": ctx_size})

if "computer_use" in enabled_tools:
    tools.append({"type": "computer"})

if "image_generation" in enabled_tools:
    tools.append({"type": "image_generation", "quality": quality, "size": size})
```

### 4.5 State-machine обработки событий потока

```python
# routers/chat.py — iterate_stream (ключевые ветви)

async def iterate_stream(s, response_id=""):
    async with s as events:
        async for event in events:
            match event:
                case ResponseCreatedEvent():
                    response_id = event.response.id

                case ResponseOutputItemAddedEvent():
                    # Создание нового шага в UI (сообщение / tool call / approval)
                    ...

                case ResponseTextDeltaEvent() | ResponseRefusalDeltaEvent():
                    # Инкрементальная доставка текста
                    yield sse_format("textDelta",
                        wrap_for_oob_swap(current_item_id, event.delta))

                case ResponseOutputItemDoneEvent():
                    # Завершение tool-вызова → запуск asyncio.Task
                    if isinstance(event.item, ResponseFunctionToolCall):
                        task = asyncio.create_task(run_function(...))
                        pending_fn_tasks[current_item_id] = task
                    elif isinstance(event.item, ResponseComputerToolCall):
                        # Computer use — выполняется последовательно позже
                        pending_computer_coros[current_item_id] = run_computer(...)

                case ResponseCompletedEvent():
                    # Сбор результатов, запись в conversation, рестарт потока
                    gathered = await asyncio.gather(
                        *pending_fn_tasks.values(), return_exceptions=True
                    )
                    # Каждый output_item пишется отдельным запросом
                    for oi in output_items:
                        await client.conversations.items.create(
                            conversation_id=conversation_id, items=[oi]
                        )
                    # Рекурсивный рестарт для продолжения диалога
                    next_stream = await client.responses.create(...)
                    async for out in iterate_stream(next_stream, response_id):
                        yield out
```

### 4.6 Выполнение кастомной функции

```python
# routers/chat.py — run_function (внутри iterate_stream)

async def run_function(name, args, cid, fn_registry, tpl_registry) -> ToolTaskResult:
    result: FunctionResult[Any] = await fn_registry.call(name, args, context=Context())

    # Рендер результата через шаблон (если задан) или JSON-<pre>
    if name in tpl_registry:
        html = templates.get_template(tpl_registry[name]).render(tool=result)
    else:
        html = f"<pre>{json.dumps(result.model_dump(exclude_none=True), indent=2)}</pre>"

    # Output item для записи в conversation
    output_item = {
        "type": "function_call_output",
        "call_id": cid,
        "output": json.dumps(result.model_dump(exclude_none=True))
    }
    return ToolTaskResult(sse_events=[("toolOutput", html)], output_item=output_item)
```

### 4.7 Пример кастомной функции (get_weather)

```python
# utils/custom_functions.py

def get_weather(
    location: Annotated[str, Field(description="The location to get weather reports for")],
    dates: Annotated[Sequence[str | datetime], Field(description="The dates to get weather reports for")] = [datetime.now().astimezone()]
) -> list[dict[str, Any]]:
    """
    Retrieves weather reports for a given location over a date range.
    """
    weather_reports = []
    for date in dates:
        weather_reports.append({
            "location": location,
            "date": date,
            "temperature": random.randint(50, 80),
            "unit": "F",
            "conditions": random.choice(["Cloudy", "Sunny", "Rainy", "Snowy", "Windy"]),
        })
    return weather_reports
```

### 4.8 Computer use — выполнение действий в браузере

```python
# utils/computer_use.py — BrowserSession.execute (упрощённо)

async def execute(self, action: Action) -> str:
    page = await self._ensure_page()
    match action.type:
        case "click":
            await page.mouse.click(action.x, action.y, button=_map_button(action.button))
        case "type":
            await page.keyboard.type(action.text)
        case "scroll":
            await page.mouse.move(action.x, action.y)
            await page.mouse.wheel(action.scroll_x, action.scroll_y)
        case "keypress":
            combo = "+".join(_map_key(k) for k in action.keys)
            await page.keyboard.press(combo)
        case "screenshot":
            pass  # скриншот ниже
    png_bytes = await page.screenshot(type="png")
    return base64.b64encode(png_bytes).decode("ascii")
```

### 4.9 Транскрибация аудио (Whisper)

```python
# routers/audio.py

@router.post("/transcribe")
async def transcribe_audio(audio: Annotated[UploadFile, File()]) -> PlainTextResponse:
    load_dotenv(override=True)
    client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    transcription = await client.audio.transcriptions.create(
        model="whisper-1",
        file=(audio.filename, await audio.read(), audio.content_type),
    )
    return PlainTextResponse(transcription.text)
```

### 4.10 MCP approval (одобрение вызова инструмента)

```python
# routers/chat.py — approve_mcp_tool

await client.conversations.items.create(
    conversation_id=conversation_id,
    items=[{
        "type": "mcp_approval_response",
        "approval_request_id": approval_request_id,
        "approve": approve,
        **({"reason": reason} if reason else {})
    }]
)
# После решения пользователя запускается новый SSE-цикл
```

---

## 5. Мультиагентное использование

### 5.1 Текущее состояние: один ассистент на диалог

В текущей архитектуре приложение работает с **одной моделью (одним ассистентом)** в
рамках диалога. Конфигурация (модель, инструкции, инструменты) задаётся глобально в
`.env` и применяется ко всем диалогам. Нет концепции нескольких агентов с разными
ролями, общающихся друг с другом.

### 5.2 Что близко к мультиагентности

| Механизм | Как связано с мультиагентностью |
|---|---|
| **Параллельные tool-вызовы** | Модель может одновременно вызывать несколько функций (`parallel_tool_calls=True`, `asyncio.gather`). Это параллелизм инструментов, но не агентов. |
| **MCP-серверы** | Внешние «агенты» по протоколу MCP — каждый со своим набором инструментов. Но они вызываются одной моделью, а не общаются между собой. |
| **Computer use** | Модель управляет отдельным браузером (своя сессия на `conversation_id`). Можно рассматривать как «агента-исполнителя», но он не принимает самостоятельных решений. |
| **Рестарт потока** | После выполнения инструментов модель вызывается повторно — это цикл «вопрос → действие → ответ», но в рамках одного агента. |

### 5.3 Что нужно для полноценной мультиагентности

Приложение **не поддерживает** сценарии, где несколько AI-агентов с разными моделями
и инструкциями общаются друг с другом (agent-to-agent communication). Для этого
потребовалось бы:

1. **Конфигурация нескольких ассистентов** — отдельные наборы (модель, инструкции,
   инструменты) для каждого агента, а не одна глобальная конфигурация в `.env`.
2. **Маршрутизация сообщений между агентами** — оркестратор, направляющий вывод одного
   агента на вход другого.
3. **Независимые conversation** — у каждого агента свой `conversation_id` или
   общий с ролями.
4. **Визуализация в UI** — отображение нескольких потоков сообщений с указанием,
   какой агент что сказал.

Текущая архитектура (единый `conversation_id` в URL, глобальный `RESPONSES_MODEL`,
одна `iterate_stream`) не предусматривает этих возможностей.

### 5.4 Возможный путь расширения

Базис для мультиагентности частично заложен:
- `ToolRegistry` — реестр функций, который можно разделить по агентам;
- `ComputerSessionManager` — менеджер сессий по `conversation_id`, который можно
  адаптировать для разделения контекстов агентов;
- MCP — стандарт для взаимодействия между инструментами, который можно использовать
  для связи агентов.

Однако реализация мультиагентного оркестратора потребует существенной переработки
`routers/chat.py` и UI.

---

## 6. Архитектура взаимодействия с AI

### 6.1 Поток данных (жизненный цикл сообщения)

```
Пользователь (браузер)
  │
  │  POST /chat/{id}/send  (multipart: текст + изображения)
  ▼
routers/chat.py: send_message
  │  1. Загрузка изображений → OpenAI Files API (purpose="vision")
  │  2. Запись сообщения → conversations.items.create
  │  3. Возврат HTML: user-message + assistant-run (с SSE-подключением)
  ▼
Браузер: HTMX вставляет фрагмент → sse.js открывает EventSource
  │
  │  GET /chat/{id}/receive  (SSE)
  ▼
routers/chat.py: stream_response → event_generator()
  │  1. Чтение конфигурации из .env (модель, инструкции, инструменты)
  │  2. Сборка tools[] из ENABLED_TOOLS + tool.config.json
  │  3. client.responses.create(stream=True)
  │  4. iterate_stream() — state-machine обработки ~20 типов событий
  │     ├─ textDelta → SSE "textDelta" (инкрементальный Markdown)
  │     ├─ function_call → asyncio.Task (параллельное выполнение)
  │     ├─ computer_call → последовательное выполнение (Playwright)
  │     ├─ mcp_approval → SSE "mcpApprovalRequest" (ожидание пользователя)
  │     └─ ResponseCompleted:
  │        ├─ gather результатов tool-задач
  │        ├─ запись output_items в conversation (по одному!)
  │        └─ рестарт responses.create (рекурсивный iterate_stream)
  ▼
Браузер: stream-md.js
  │  textDelta → marked.parse() + DOMPurify.sanitize() → DOM
  │  toolOutput → HTMX-своп фрагмента
  │  endStream → закрытие EventSource
```

### 6.2 Где выполняются инструменты

| Тип инструмента | Где выполняется | Кто возвращает результат модели |
|---|---|---|
| **Code interpreter** | Серверы OpenAI (песочница container) | OpenAI (встроенный) |
| **File search** | Серверы OpenAI (Vector Store) | OpenAI (встроенный) |
| **Web search** | Серверы OpenAI | OpenAI (встроенный) |
| **Image generation** | Серверы OpenAI | OpenAI (встроенный) |
| **Custom functions** | Сервер приложения (Python) | Приложение → `conversations.items.create` |
| **MCP** | Внешний MCP-сервер | Приложение (релей) → `conversations.items.create` |
| **Computer use** | Сервер приложения (Playwright headless Chromium) | Приложение → `conversations.items.create` |

### 6.3 Конфигурация ассистента

Вся конфигурация хранится локально (OpenAI не хранит настройки ассистента — ключевое
отличие от Assistants API):

| Параметр | Где хранится | Пример |
|---|---|---|
| `OPENAI_API_KEY` | `.env` | `sk-...` |
| `RESPONSES_MODEL` | `.env` | `gpt-5-mini` |
| `RESPONSES_INSTRUCTIONS` | `.env` | `Ты — helpful assistant` |
| `ENABLED_TOOLS` | `.env` (CSV) | `file_search,code_interpreter,function` |
| `SHOW_TOOL_CALL_DETAIL` | `.env` | `true` |
| `VECTOR_STORE_ID` | `.env` (автозаполнение) | `vs_abc123` |
| Custom functions | `tool.config.json` | name, import_path, template_path |
| MCP servers | `tool.config.json` | server_label, server_url, require_approval |
| `WEB_SEARCH_*` | `.env` | context_size, location |
| `IMAGE_GENERATION_*` | `.env` | quality, size, background |
| `COMPUTER_USE_DISPLAY_*` | `.env` | width, height |

Конфигурация **перечитывается на каждый запрос** (`load_dotenv(override=True)`), поэтому
изменения через `/setup` применяются мгновенно без перезапуска.

---

## 7. Ограничения и нюансы

### 7.1 Архитектурные ограничения

- **Нет аутентификации** — все эндпоинты открыты; шаблон рассчитан на локальный запуск.
- **Один провайдер** — только OpenAI; нет абстракции над провайдерами моделей.
- **Один ассистент** — глобальная конфигурация для всех диалогов; нет per-conversation
  настроек модели/инструкций.
- **Нет БД** — всё состояние: `.env`, `tool.config.json`, `uploads/`, память процесса
  (Playwright-сессии), сторона OpenAI (conversations).
- **Нет мультиагентности** — нет оркестратора для связи нескольких AI-агентов.

### 7.2 Известные проблемы

1. **`download_container_file` мутирует общий `client.base_url`** — гонка при
   параллельных запросах к разным container_id (`routers/files.py:366-368`).
2. **`update_env_file` не потокобезопасен** — конкурентные записи через `/setup`
   могут привести к потере данных.
3. **Image generation** — упоминается в коде, но README отмечает, что шаблон «пока не
   поддерживает генерацию изображений» (обработка событий реализована, но может быть
   нестабильной).
4. **`utils/threads.py`** — мёртвый код (legacy Assistants API); не использовать.
5. **`utils/streaming.py:ResponseStreamState`** — неиспользуемый артефакт.
6. **MCP approval workaround** — дополнительный коммит item в conversation для обхода
   бага Responses API (фиксация state на стороне OpenAI).

### 7.3 Параллелизм tool-вызовов

- **Function calls** — выполняются параллельно через `asyncio.gather(return_exceptions=True)`.
- **Computer use calls** — выполняются **строго последовательно** (гонки в браузере).
- **Output items** записываются в conversation **по одному** (батч-отправка приводит
  к тихому дропу на стороне OpenAI).

### 7.4 Обработка ошибок

Приложение использует стратегию **graceful degradation**: вместо 500-х ошибок рендерятся
HTML-фрагменты с описанием ошибки. Catch-all `except Exception` (правило `BLE001` отключено
в `ruff`) — намеренное архитектурное решение. В SSE-потоке при ошибке эмитятся
`runCompleted` + `networkError` + `endStream=ERROR`, чтобы клиент не «завис».

---

## Краткое резюме

| Аспект | Значение |
|---|---|
| **Провайдер AI** | OpenAI (единственный) |
| **API** | Responses API (`/v1/responses`) + Conversations + Files + Vector Stores + Audio |
| **Модели** | 19 моделей (gpt-4.x, gpt-5.x, o1/o3/o4, gpt-oss); выбор через `/setup` |
| **Транспорт** | SSE (Server-Sent Events) с HTMX на клиенте |
| **Инструменты** | 7 типов: code interpreter, file search, custom functions, MCP, web search, computer use, image generation |
| **Мультиагентность** | Не поддерживается (один ассистент, глобальная конфигурация) |
| **Состояние диалога** | На стороне OpenAI (Conversation API) |
| **Мультимодальность** | Текст + изображения (vision) + аудио (Whisper) |
| **Конфигурация** | Локальная: `.env` + `tool.config.json`; перечитывается на каждый запрос |
