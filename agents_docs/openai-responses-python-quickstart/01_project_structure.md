# 01. Карта проекта (Project Structure)

## Назначение

`openai-responses-python-quickstart` — монолитный шаблон-стартер для создания чат-приложений поверх **OpenAI Responses API** (`/v1/responses`), написанный на Python 3.13 + FastAPI + Jinja2 + HTMX. Функциональность: потоковый чат через Server-Sent Events (SSE) с инкрементальным рендерингом Markdown, локальная конфигурация ассистента (модель, инструкции, инструменты) без хранения состояния на стороне OpenAI, семь типов инструментов (code interpreter, file search, custom functions, MCP, web search, computer use, image generation), управление файлами через Vector Store, транскрибация аудио (Whisper) и потоковый протокол визуализации tool-вызовов. Сервер является тонким посредником (proxy/orchestrator) между браузером и OpenAI API; вся бизнес-логика ограничена одним процессом, БД и брокеры сообщений отсутствуют.

## Дерево директорий и ключевых файлов

```
openai-responses-python-quickstart/
├── main.py                          # Точка входа FastAPI: lifespan, монтирование роутеров,
│                                    #   глобальные exception-handlers, GET / (домашняя страница)
├── pyproject.toml                   # uv-проект: зависимости, dev-группа, конфиг ruff, маркеры pytest
├── uv.lock                          # Зафиксированный граф зависимостей (uv sync)
├── .python-version                  # Пинит Python 3.13
├── .env.example                     # Образец переменных окружения
├── .env                             # Runtime-конфиг (создаётся через /setup, в gitignore)
├── tool.config.json                 # Реестр custom functions + MCP-серверов (генерируется в lifespan)
├── AGENTS.md                        # Универсальные инструкции для всех AI-харнесов (EN)
├── AGENTS.ru.md                     # То же на русском
├── CLAUDE.md                        # Инструкции для Claude Code — специфика + ссылка на AGENTS.md (EN)
├── CLAUDE.ru.md                     # То же на русском
├── .github/copilot-instructions.md  # Инструкции для GitHub Copilot (Chat/Edits/code review)
├── README.md                        # Инструкция по запуску и обзор архитектуры (EN)
├── README.ru.md                     # То же на русском
│
├── routers/                         # HTTP-слой (FastAPI APIRouter'ы)
│   ├── __init__.py                  # Пустой
│   ├── chat.py                      # ЯДРО: POST /send, SSE GET /receive (state-machine событий
│   │                                #   Responses API), POST /approve (MCP-апрув). Самый сложный файл
│   │                                #   (779 строк): стриминг, параллельные tool-вызовы, рестарт потока
│   ├── files.py                     # Файлы: list/upload/delete/delete-all, vector store,
│   │                                #   скачивание локальных и container-файлов (code interpreter)
│   ├── setup.py                     # Страница /setup: сохранение .env, реестр функций/MCP, web_search,
│   │                                #   image_generation конфиг, HTMX-фрагменты для динамических строк
│   └── audio.py                     # POST /audio/transcribe: Whisper (whisper-1)
│
├── utils/                           # Сервисный слой (независим от HTTP)
│   ├── __init__.py                  # Пустой
│   ├── config.py                    # Pydantic-модели CustomFunction/ToolConfig, чтение/запись .env
│   │                                #   и tool.config.json (update_env_file, generate_registry_file)
│   ├── function_calling.py          # ToolRegistry (реестр кастомных функций), ToolRegistration,
│   │                                #   FunctionResult[T], Context, иерархия исключений Tool*Error
│   ├── function_definitions.py      # Интроспекция сигнатур функций → Pydantic-модели аргументов и
│   │                                #   JSON Schema для tool-дефиниций (код заимствован из FastMCP)
│   ├── computer_use.py              # Computer use: протоколы ComputerSession/ComputerSessionManager,
│   │                                #   реализация BrowserSession (headless Playwright Chromium),
│   │                                #   синглтон session_manager, маппинг клавиш, describe_actions
│   ├── files.py                     # Хелперы vector store (get_or_create, пагинация), локальное
│   │                                #   хранилище uploads/ (store/retrieve/delete_local_file)
│   ├── conversations.py             # create_conversation() — создание conversation на стороне OpenAI
│   ├── threads.py                   # create_thread() — МЁРТВЫЙ КОД: legacy Assistants API (beta.threads)
│   ├── streaming.py                 # ResponseStreamState (dataclass-артефакт, фактически не используется)
│   │                                #   + stream_file_content (async-генератор байтов)
│   ├── sse.py                       # sse_format(event, data) — форматтер SSE-сообщений
│   ├── tool_tasks.py                # ToolTaskResult (dataclass): SSE-события + output item для
│   │                                #   conversations.items.create после выполнения tool
│   └── custom_functions.py          # Пример кастомной функции get_weather (случайные данные)
│
├── templates/                       # Jinja2-шаблоны
│   ├── layout.html                  # Базовый каркас: nav, подключение htmx/sse/marked/DOMPurify/JS
│   ├── index.html                   # Чат: форма отправки, загрузка изображений, кнопка микрофона
│   ├── setup.html                   # Страница конфигурации (модель, инструкции, инструменты, MCP)
│   ├── error.html                   # Общая страница ошибки
│   └── components/
│       ├── assistant-run.html       # Точка подключения SSE: sse-connect к /receive, список событий
│       ├── assistant-step.html      # Универсальный шаг (toolCall <details>, сообщение, approval)
│       ├── user-message.html        # Пузырь пользователя (+ миниатюры загруженных изображений)
│       ├── weather-widget.html      # Пример template для FunctionResult (get_weather)
│       ├── mcp-approval-request.html# UI-карточка одобрения MCP-вызова (Approve/Reject + reason)
│       ├── file-viewer.html         # Менеджер файлов (upload form + список)
│       ├── file-list.html           # Список файлов с пагинацией и кнопками удаления
│       ├── file-list-page.html      # Фрагмент пагинации (hx-swap-oob append)
│       ├── file-card.html           # Карточка файла в карусели (img/link)
│       ├── registry-row.html        # Строка кастомной функции (name/import/template)
│       ├── mcp-row.html             # Строка MCP-сервера (label/url/connector/auth/headers/approval)
│       ├── loading-dots.html        # Индикатор "печатает..."
│       └── network-error.html       # Баннер сетевой ошибки
│
├── static/                          # Статика (vender и кастом)
│   ├── styles.css                   # Все стили приложения
│   ├── htmx.min.js                  # HTMX (vendor)
│   ├── sse.js                       # Расширение HTMX SSE (vendor)
│   ├── stream-md.js                 # КАСТОМ: обработка textDelta/toolDelta/textReplacement,
│   │                                #   накопительный рендер Markdown (marked + DOMPurify),
│   │                                #   OOB-swap-парсер, управление кнопкой Send, network-error,
│   │                                #   превью изображений
│   └── audio-recorder.js            # MediaRecorder → FormData → POST /audio/transcribe
│
├── uploads/                         # Локальные копии файлов (создаётся при первом upload)
│
├── tests/                           # 18 файлов, ~194 теста
│   ├── conftest.py                  # REAL_API_KEY, _dotenv-менеджер, app_server (uvicorn в потоке),
│   │                                #   parse_sse_events, Playwright-фикстуры env_*_only, патчи anyio
│   ├── test_parallel_tools.py       # Параллельные function/computer вызовы, порядок результатов,
│   │                                #   отмена задач, MCP approval + function, text-only
│   ├── test_tool_output_rendering.py# Рендер toolOutput, web search tool payload, url_citation,
│   │                                #   image generation события
│   ├── test_setup_page_rendering.py # Playwright: условный рендер /setup под каждую комбинацию env
│   ├── test_computer_use.py         # BrowserSession (реальный headless Chromium), _KEY_MAP, менеджер
│   ├── test_code_interpreter_image_output.py # Аннотации container_file_citation → imageOutput
│   ├── test_file_carousel.py        # Карусель container-файлов code interpreter
│   ├── test_file_upload.py          # Мульти-аплоад + eventual consistency (merge вручную)
│   ├── test_file_delete.py          # Удаление с учётом отставания API
│   ├── test_file_delete_all.py      # Пагинированное удаление всех файлов
│   ├── test_file_list_pagination.py # Пагинация списка файлов (unit, mocked)
│   ├── test_image_upload.py         # Отправка изображений в чат (vision)
│   ├── test_audio_transcription.py  # POST /audio/transcribe (mocked)
│   ├── test_web_search_live.py      # [live] реальный web_search
│   ├── test_image_upload_live.py    # [live] vision-конвейер через реальный API
│   ├── test_image_generation_live.py# [live] image_generation события
│   └── test_file_list_pagination_live.py # [live] пагинация на реальном vector store
│
├── .github/workflows/release.yml    # CI: авто-инкремент patch-версии + GitHub Release на push в main
├── .claude/
│   ├── settings.local.json          # Разрешения + Stop-hook на lint/typecheck
│   └── hooks/lint-and-typecheck.sh  # Запускает `uv run ruff check` и `uv run ty check` после каждой
│                                    #   итерации Claude Code (блокирует Stop при ошибках)
└── docs/                            # Данная документация
```

## Абстракции по модулям

| Модуль | Ключевые абстракции |
|---|---|
| `utils/function_calling.py` | `ToolRegistry`, `ToolRegistration`, `FunctionResult[T]`, `Context`, `ToolRuntimeError` / `ToolNotFoundError` / `ToolCallError` |
| `utils/function_definitions.py` | `FuncMetadata`, `ArgModelBase`, `func_metadata()`, кастомный `StrictJsonSchema` |
| `utils/computer_use.py` | `ComputerSession` / `ComputerSessionManager` (протоколы, `@runtime_checkable`), `BrowserSession`, `BrowserSessionManager`, тип-алиас `Action` |
| `utils/config.py` | `CustomFunction`, `ToolConfig` (Pydantic) |
| `routers/chat.py` | нет классов — функциональная state-machine над потоком `ResponseStreamEvent` |
| `utils/streaming.py` | `ResponseStreamState` (dataclass; не используется в рабочем коде) |

## Внешние зависимости и их роль

| Внешняя система | Роль | Точки использования |
|---|---|---|
| **OpenAI API (Responses API)** | Ядро: генерация ответов, стриминг, conversation state, tool execution | `routers/chat.py`, `utils/conversations.py` |
| **OpenAI Files API** | Загрузка изображений (purpose=`vision`), файлов для поиска, скачивание контента | `routers/chat.py`, `routers/files.py`, `routers/audio.py` |
| **OpenAI Vector Stores API** | Хранилище документов для `file_search`, пагинация списков | `utils/files.py`, `routers/files.py` |
| **OpenAI Containers API** | Песочница `code_interpreter`: список/скачивание сгенерированных файлов | `routers/chat.py`, `routers/files.py` |
| **OpenAI Audio API (Whisper)** | Транскрибация голосовых сообщений | `routers/audio.py`, `static/audio-recorder.js` |
| **Playwright (Chromium)** | Headless-браузер для `computer_use` | `utils/computer_use.py` |
| **MCP-серверы** (внешние, задаются в `tool.config.json`) | Удалённые инструменты по протоколу MCP | `routers/chat.py` (передача в API), `routers/setup.py` |
| **Локальная ФС (`uploads/`)** | Копии загруженных файлов (OpenAI не отдаёт их по HTTP) | `utils/files.py`, `routers/files.py` |

БД, брокеры сообщений и кэш-серверы отсутствуют; всё состояние — в `.env`, `tool.config.json`, `uploads/`, в памяти процесса (Playwright-сессии) и на стороне OpenAI (conversation items).
