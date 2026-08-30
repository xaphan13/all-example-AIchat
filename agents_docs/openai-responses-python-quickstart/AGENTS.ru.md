# AGENTS.md — инструкции для AI-ассистентов

> Универсальный файл-инструкция для всех AI-харнесов: Koda, Claude Code, Cursor,
> GitHub Copilot, OpenAI Codex, Gemini CLI и др. Специфика конкретных инструментов —
> в их собственных файлах (`CLAUDE.md`, `.github/copilot-instructions.md`).

## 1. Что это за проект

`openai-responses-python-quickstart` — монолитный шаблон-стартер чат-приложения
поверх **OpenAI Responses API**: Python 3.13 + FastAPI + Jinja2 + HTMX.

Сервер — тонкий посредник (proxy/orchestrator) между браузером и OpenAI API:

- потоковый чат через **SSE** с инкрементальным рендерингом Markdown на клиенте;
- **локальная конфигурация ассистента** (модель, инструкции, инструменты) в `.env`
  и `tool.config.json` — OpenAI не хранит конфигурацию (принципиальное отличие от Assistants API);
- состояние разговора хранится на стороне OpenAI — сервер передаёт только `conversation_id`;
- семь типов инструментов: code interpreter, file search, custom functions, MCP, web search,
  computer use, image generation (генерация изображений в шаблоне пока не реализована);
- файлы (Vector Store), транскрибация аудио (Whisper), computer use на базе headless Playwright.

**Документация (на русском, папка `docs/`):** все доки написаны на русском.
Перед серьёзными изменениями прочитай `01` и `02` — это избавит от необходимости
обходить весь код.

| Файл | Что внутри |
|---|---|
| `docs/01_project_structure.md` | Полная карта проекта: дерево директорий с аннотациями, абстракции по модулям, таблица внешних зависимостей |
| `docs/02_architecture.md` | Высокоуровневая архитектура, ключевые решения, таблица паттернов, диаграммы потоков данных (SSE-конвейер, MCP approval, файлы), состояние/кэширование/конкурентность |
| `docs/03_execution_flow.md` | Жизненный цикл приложения (startup/shutdown), ключевые бизнес-процессы по шагам (setup, send-message, stream_response, MCP approval, файлы, аудио), таблица роутинга, обработка ошибок и логирование |
| `docs/04_code_quality.md` | Обзор качества: читаемость, модульность, SOLID/DRY/KISS/YAGNI, 10 запахов кода с локациями, узкие места, риски безопасности, оценки (0–5) |
| `docs/05_optimization_roadmap.md` | Приоритизированная дорожная карта (P0–P2): фикс path traversal, вынос состояния, рефакторинг stream state-machine, TTL для Playwright, SSE heartbeat, CI/CD |

## 2. Обязательные инструменты и команды

- Управление зависимостями — **только `uv`**. Никогда не используй `pip`, `poetry` и т.п.
- Python 3.13 (зафиксирован в `.python-version`).

| Действие | Команда |
|---|---|
| Установка зависимостей | `uv sync` |
| Dev-сервер | `uv run uvicorn main:app --reload` (http://localhost:8000) |
| Линт | `uv run ruff check` |
| Проверка типов | `uv run ty check` |
| Тесты (без live) | `uv run pytest -m "not live"` |
| Тесты (все, с реальным API) | `uv run pytest` (нужен валидный `OPENAI_API_KEY`) |
| Установка браузера для computer use | `uv run playwright install chromium` |

Перед первым запуском нужен `.env`: минимум `OPENAI_API_KEY` и `RESPONSES_MODEL`
(образец — `.env.example`; заполняется вручную или через страницу `/setup`).

## 3. Архитектура (кратко)

```
main.py            — точка входа: lifespan, монтирование роутеров, глобальные exception-handlers, GET /
routers/           — HTTP-слой (FastAPI APIRouter'ы)
  chat.py          — ЯДРО: POST /send, SSE GET /receive (state-machine iterate_stream), POST /approve
  files.py         — файлы: upload/list/delete, vector store, скачивание container-файлов
  setup.py         — /setup: .env, реестр custom functions + MCP, web_search/image_generation конфиг
  audio.py         — POST /audio/transcribe (Whisper)
utils/             — сервисный слой (не зависит от HTTP)
  config.py        — Pydantic-модели CustomFunction/ToolConfig, чтение/запись .env и tool.config.json
  function_calling.py — ToolRegistry, FunctionResult[T], Context, иерархия Tool*Error
  function_definitions.py — интроспекция сигнатур функций → JSON Schema для tool-дефиниций
  computer_use.py  — протоколы ComputerSession/ComputerSessionManager + BrowserSession (Playwright)
  files.py         — хелперы vector store, локальное хранилище uploads/
  sse.py           — sse_format(event, data)
  tool_tasks.py    — ToolTaskResult (SSE-события + output item)
templates/         — Jinja2: layout.html, index.html, setup.html, components/
static/            — styles.css, htmx/sse.js (vendor), stream-md.js (кастом), audio-recorder.js
tests/             — pytest, ~194 теста; *_live.py требуют реальный ключ
tool.config.json   — реестр custom functions + MCP-серверов (генерируется в lifespan)
```

## 4. Правила разработки

- **TDD**: сначала пиши тест, затем реализацию.
- Работай в **feature-ветках**: `gh issue develop <НОМЕР_ЗАДАЧИ>`.
- Вноси **минимальные изменения** для решения задачи; не рефактори «по пути» без необходимости.
- Следуй существующим идиомам Python 3.13: `match/case`, `Annotated[...]`, `str | None`
  (вместо `Optional`), keyword-only параметры, async I/O, докстринги с пояснением «почему».
- Комментарии и докстринги в коде — **на русском** (следуй стилю репозитория).
- Перед завершением работы обязательно прогоняй: `uv run ruff check` + `uv run ty check`
  + `uv run pytest -m "not live"`.
- Не запускай `git commit`/`push`/другие git-мутации без явной команды пользователя.

## 5. Важные нюансы (читай перед изменениями)

1. **`routers/chat.py` — самый сложный файл.** `iterate_stream()` — state-machine
   обработки ~20 типов событий Responses API. Рестарт потока после tool-вызовов — рекурсивный
   (`responses.create` вызывается заново). Меняй осторожно и проверяй тестами
   (`tests/test_parallel_tools.py`, `tests/test_tool_output_rendering.py`).
2. **Параллельность tool-вызовов:** function-вызовы собираются в `asyncio.Task` и выполняются
   через `gather(return_exceptions=True)`, а computer-use-вызовы — **строго последовательно**
   (иначе гонки в браузере). Не меняй это без веской причины.
3. **Output items пишутся в conversation по одному** — батч приводит к «тихому» дропу
   на стороне OpenAI (есть комментарий в `routers/chat.py`). Сохраняй это поведение.
4. **`routers/files.py:download_container_file` мутирует общий `client.base_url`** — известная
   гонка. В новых местах не усугубляй: для container-скачиваний создавай отдельный клиент.
5. **Catch-all `except Exception` границы (`BLE001` отключён в `pyproject.toml`) — намеренны:**
   шаблон деградирует через error-части вместо 500. Не «улучшай» их без необходимости.
6. **Live-тесты** (`*_live.py`, маркер `live`) бьют в реальный OpenAI API. В CI и обычных
   прогонах — только `-m "not live"`.
7. **Мёртвый код:** `utils/threads.py` (legacy Assistants API) и
   `utils/streaming.py:ResponseStreamState` (не используется) — не строй ничего поверх них.
8. **Playwright-сессии (computer use)** живут в памяти процесса до shutdown и закрываются
   через `session_manager.close_all()` в lifespan. Новые бэкенды — только через протоколы
   `ComputerSession`/`ComputerSessionManager` (это позволит подменить Playwright без правки `routers/chat.py`).
9. **Конфигурация перечитывается на каждый запрос** (`load_dotenv(override=True)` в теле
   роутеров) — так правки через `/setup` применяются без рестарта. Не «оптимизируй» это
   кэшированием в обход roadmap (`docs/05_optimization_roadmap.md`).

## 6. Тестирование

- Юнит/интеграционные тесты с моками — обычный режим. Мок-инфраструктура в `tests/conftest.py`:
  `_FAKE_API_KEY`, хелперы построения потоков событий, Playwright-фикстуры, патчи anyio.
- Есть реальные Playwright-тесты (`test_computer_use.py`, `test_setup_page_rendering.py`) —
  требуют установленного Chromium (`uv run playwright install chromium`).
- Новую функциональность покрывай тестами в том же стиле.
