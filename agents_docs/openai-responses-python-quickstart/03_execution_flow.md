# 03. Логика и работа кода (Execution Flow)

## 1. Жизненный цикл приложения

### 1.1 Инициализация (startup)

1. `uv run uvicorn main:app --reload` (или `python main.py` → `uvicorn.run(app, host="0.0.0.0", port=8000)`).
2. Импорт `main.py`:
   - создаётся логгер `logging.getLogger("uvicorn.error")`;
   - создаётся `FastAPI(lifespan=lifespan)`;
   - монтируются роутеры: `audio.router` (`/audio`), `chat.router` (`/chat/{conversation_id}`), `files.router` (`/files`), `setup.router` (`/setup`);
   - монтируются статика `/static` и `Jinja2Templates(directory="templates")`.
3. Старт lifespan (`main.py:23`):
   - если нет `tool.config.json` — создаётся дефолтный конфиг с `get_weather` (запись вынесена в `asyncio.to_thread`, чтобы не блокировать event loop);
   - `yield` — приложение готово.
4. Первый запрос к `GET /`:
   - `load_dotenv(override=True)`; если отсутствуют `OPENAI_API_KEY` или `RESPONSES_MODEL` → `RedirectResponse` на `/setup`;
   - если не передан `conversation_id` → `create_conversation()` (создание conversation на OpenAI);
   - рендер `index.html` с `conversation_id`.

### 1.2 Завершение работы (shutdown)

5. После `yield` в lifespan выполняется `await session_manager.close_all()` — закрытие всех Playwright-браузеров (`BrowserSession.close()` с идемпотентной обработкой уже отключённых сессий).
6. Прочие ресурсы (клиенты `AsyncOpenAI`, SSE-генераторы) закрываются/утилизируются средствами процесса; явного graceful-обрыва активных SSE нет.

## 2. Ключевые бизнес-процессы

### 2.1 Конфигурация через /setup (`routers/setup.py`)

- `GET /setup/` (`read_setup`) — читает текущее состояние env и `tool.config.json`, нормализует `require_approval` MCP-серверов (str/dict → `always`/`never`), рендерит `setup.html`. Хардкод-список `available_models` (`gpt-4.1…gpt-oss-20b`) — модели не запрашиваются у API.
- `POST /api-key` (`set_openai_api_key`) — санитизирует значение (strip, удаление `\r\n`) и пишет в `.env` через `update_env_file`.
- `POST /config` (`save_app_config`) — один endpoint, четыре ветки по `action`:
  1. `regenerate_registry`: собирает кастомные функции (name/import_path/template_path) и MCP-серверы из повторяющихся Form-полей; при пустом вводе **сохраняет существующие** записи (`read_registry_entries()` / `read_mcp_servers()`); валидирует JSON-заголовки; пишет `tool.config.json` через `generate_registry_file()`.
  2. `save_web_search_config`: валидирует `search_context_size` ∈ {low, medium, high} и пишет `WEB_SEARCH_*` в `.env`.
  3. `save_image_generation_config`: валидирует quality/size/background и пишет `IMAGE_GENERATION_*`.
  4. default: валидирует `model`/`instructions`, пишет `RESPONSES_MODEL`, `RESPONSES_INSTRUCTIONS`, `ENABLED_TOOLS` (CSV), `SHOW_TOOL_CALL_DETAIL`.
  - Все ошибки перехватываются блоком `except Exception` и возвращаются как `status=error&message_text=...` (редирект 303).
- `GET/DELETE /registry-row`, `GET/DELETE /mcp-row` — HTMX-фрагменты для динамического добавления/удаления строк; индекс вычисляется из длин входящих списков `hx-include`.

### 2.2 Отправка сообщения в чат (`routers/chat.py:send_message`)

1. Формирует контент первого элемента: `{"type": "input_text", "text": f"System: Today's date is {…}\n{userInput}"}` — подстановка даты в системную часть.
2. Для каждого `UploadFile` (image): `await image.read()` → `client.files.create(purpose="vision")` → добавляет `{"type": "input_image", "file_id": …}`.
3. Пишет в conversation: `client.conversations.items.create(type="message", role="user", content=[...])`.
4. Возвращает `HTMLResponse(user_message_html + assistant_run_html)` — HTMX вставит фрагменты в `#messages` (`hx-swap="beforeend"`), после чего `sse.js` откроет EventSource на `/chat/{id}/receive`.

### 2.3 Потоковая генерация ответа (`routers/chat.py:stream_response`)

Сборка инструментов (шаг 2 event_generator):

| `ENABLED_TOOLS` | Payload в `tools[]` |
|---|---|
| `file_search` | `{"type": "file_search", "vector_store_ids": [VECTOR_STORE_ID]}` (id валидируется `isalnum`) |
| `code_interpreter` | `{"type": "code_interpreter", "container": {"type": "auto"}}` |
| `function` | `ToolRegistry.get_tool_def_list()` — JSON Schema из сигнатур (`utils/function_definitions.py`); импорт модулей через `importlib.import_module(import_path)` |
| `mcp` | `TOOL_CONFIG.mcp_servers` (тип `Mcp` из SDK) |
| `web_search` | `{"type": "web_search_preview", "search_context_size": …, "user_location": {…}}` |
| `computer_use` | `{"type": "computer"}` (параметры экрана локальные, в API не уходят) |
| `image_generation` | `{"type": "image_generation", "quality":…, "size":…, "background":…}` |

Далее — state-machine `iterate_stream()` (см. карту событий в `docs/02_architecture.md`, §4.2). Ключевые механики:

- **`wrap_for_oob_swap(step_id, text)`** формирует `<span hx-swap-oob="beforeend:#step-{step_id}">…</span>` — дельты добавляются внутрь уже вставленного шага.
- **Функции:** на `OutputItemDone(function_call)` создаётся `asyncio.Task(run_function(...))`; результат — `ToolTaskResult(sse_events, output_item)`. На `ResponseCompleted` все tasks собираются через `gather(return_exceptions=True)`, SSE-события эмитятся **в исходном порядке вызовов** (`all_item_ids`), каждый `output_item` пишется в conversation **отдельным** запросом (комментарий в коде: батч приводит к «тихому» дропу).
- **Computer use:** coroutine сохраняется в `pending_computer_coros` и выполняется **последовательно** (обход в порядке вызовов), чтобы избежать гонок в браузере.
- **MCP approval:** на `McpApprovalRequest` дополнительно коммитится item в conversation (workaround бага Responses API — фиксация state на стороне OpenAI), рендерится карточка одобрения, `has_approval_request=True` → после `ResponseCompleted` поток завершается без рестарта.
- **Code interpreter:** на `OutputItemDone(code_interpreter_call)` запрашивается `containers.files.list`, файлы `source == "assistant"` рендерятся в карусель (`file-card.html`), которая заменяется через OOB `innerHTML:#file-carousel`.
- **Аннотации:** `file_citation` → ссылка-сноска `†` на `/files/{file_name}`; `container_file_citation` → для изображений `imageOutput` (`<img>` с `openImagePreview`), иначе `textReplacement` `sandbox:path|url`; `url_citation` → HTML-ссылка (`escape()`).
- **Рестарт потока:** если после завершения есть output_items и нет approval — `responses.create` вызывается повторно с теми же параметрами и рекурсивно передаётся в `iterate_stream`. Комментарий в коде: рестарт только один (на каждую итерацию), что исключает бесконечную рекурсию при «пустых» ответах.

### 2.4 MCP approval (`approve_mcp_tool`)

Пишет `conversations.items.create(type="mcp_approval_response", approval_request_id, approve, reason?)`; при ошибке возвращает HTML-карточку ошибки (без выброса). При успехе — `ack_html + assistant_run_html` (новый SSE-цикл продолжит обработку).

### 2.5 Файлы (`routers/files.py`, `utils/files.py`)

- `upload_file`: фаза 1 — чтение всех `UploadFile` (до закрытия объектов, с валидацией «не пустой файл / нет имени»); фаза 2 — параллельный `gather` на upload в OpenAI + добавление в vector store + локальное `store_file`; фаза 3 — повторное получение списка и **ручной merge** неотобразившихся файлов (eventual consistency).
- `delete_all_files`: пагинация по 100, затем параллельное удаление (local copy → vector store → base file object).
- `download_container_file`: получает путь файла, временно подменяет `client.base_url` на `https://api.openai.com/v1/containers/{container_id}`, вызывает `client.files.content`, возвращает `StreamingResponse` (image → inline `Content-Disposition`).

### 2.6 Аудио (`routers/audio.py`)

`POST /audio/transcribe`: создаёт локальный клиент с ключом из env → `client.audio.transcriptions.create(model="whisper-1", file=(filename, bytes, content_type))` → `PlainTextResponse(text)`.

## 3. Роутинг и middleware

- **Роуты** (сводка):

| Метод/путь | Функция | Файл |
|---|---|---|
| `GET /` | `read_home` | `main.py` |
| `POST /setup/api-key` | `set_openai_api_key` | `routers/setup.py` |
| `GET/POST /setup/`, `POST /setup/config`, `GET/DELETE /setup/registry-row`, `GET/DELETE /setup/mcp-row` | `read_setup`, `save_app_config`, `new_registry_row`, `delete_registry_row`, `new_mcp_row`, `delete_mcp_row` | `routers/setup.py` |
| `POST /chat/{id}/send`, `GET /chat/{id}/receive`, `POST /chat/{id}/approve` | `send_message`, `stream_response`, `approve_mcp_tool` | `routers/chat.py` |
| `GET /files/list`, `POST /files/`, `DELETE /files/`, `DELETE /files/{file_id}`, `GET /files/{file_name}`, `GET /files/{container_id}/{file_id}/openai_content`, `GET /files/{file_id}/content` | `list_files`, `upload_file`, `delete_all_files`, `delete_file`, `download_stored_file`, `download_container_file`, `get_assistant_image_content` | `routers/files.py` |
| `POST /audio/transcribe` | `transcribe_audio` | `routers/audio.py` |
| `GET /static/*` | StaticFiles | `main.py` |

- **Middleware:** собственных middleware нет. «Middleware-подобные» обязанности выполняют глобальные exception-handlers (`main.py:57-92`) и `Depends`-инжекции. HX-специфичность: `validation_exception_handler` различает htmx-запросы по заголовку `hx-request`.
- **Порядок регистрации:** все роутеры подключаются без конфликтов; `GET /files/{file_name}` и `GET /files/{container_id}/{file_id}/openai_content` сосуществуют благодаря более специфичным шаблонам, объявленным позже.
- **Отсутствие аутентификации** — любая страница/endpoint доступен без проверок (шаблон рассчитан на локальный запуск).

## 4. Обработка ошибок и логирование

### 4.1 Обработка ошибок

- **Глобальный `Exception` handler** (`main.py:57`) → рендер `error.html`, `status_code=500`, тело ошибки (`str(exc)`) попадает в страницу — в проде утечка деталей исключений.
- **`RequestValidationError` handler** → для htmx-запросов возвращает HTML-фрагмент с `Validation Error: ...` (status 200 — чтобы HTMX не потерял контейнер), для обычных — `error.html`, 422.
- **`HTTPException` handler** → `error.html` с кодом исключения.
- **Внутри SSE-генератора** (`iterate_stream`): `except Exception` → логирование `Network/stream error`, эмит `runCompleted` (очистка лоадера), `networkError`, `endStream=ERROR` — клиент не «подвисает».
- **`asyncio.CancelledError`** → отмена фоновых задач (`task.cancel()` + `gather`), повторный `raise`.
- **Tool-задачи:** `gather(return_exceptions=True)`; упавшие задачи дают SSE `toolOutput` с `<pre>Error: ...</pre>` и `function_call_output` c `{"error": ...}` — модель видит ошибку и может ответить пользователю.
- **Failsafe в файлах:** каждый сетевой вызов оборачивается в try/except, ошибки агрегируются в `error_messages` и показываются в UI, не роняя остальной ответ.
- **Failsafe в setup:** `save_app_config` перехватывает всё и редиректит с `status=error`.
- **Failsafe в MCP approval:** ошибка записи `mcp_approval_response` → HTML-карточка с текстом ошибки (можно повторить).

### 4.2 Логирование

- Единственный логгер на всё приложение: `logging.getLogger("uvicorn.error")` (переиспользуется из `main.py`, `routers/*`, `utils/*`).
- Уровни: `info` — lifecycle-события (загрузка страниц, upload/delete файлов), `error` — исключения, `debug` — отладочные детали (`update_env_file`, коммит approval request), `warning` — частичные сбои.
- **Нет** структурированного логирования (JSON), **нет** request-id/корреляционных идентификаторов; логирование ошибок дублируется во вложенных слоях (например, `utils/files.py` логирует, потом `routers/files.py` логирует снова).
- На клиенте `stream-md.js` активно использует `console.log/warn/error` (включая отладочные `console.log("disableSendButton: ...")`) — шумно, но не влияет на функциональность.
