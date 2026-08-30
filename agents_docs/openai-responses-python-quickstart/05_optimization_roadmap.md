# 05. Предложения по развитию (Optimization Roadmap)

Приоритеты: **P0** — безопасность/надёжность, **P1** — архитектура и производительность, **P2** — DX и тесты.

## 1. Архитектурные улучшения

### P0-1. Устранить path traversal при upload
`utils/files.py:store_file` записывает по имени пользователя без проверок. Внести общую функцию санитизации имени (`secure_filename`-эквивалент) и переиспользовать её в `store_file` / `retrieve_file` / `delete_local_file`:
```python
def _safe_filename(name: str) -> str:
    name = Path(name).name            # отбросить любые пути
    return re.sub(r"[^\w.\-]", "_", name)
```
Добавить тест с `"../../evil.txt"` и Windows-разделителями.

### P0-2. Вынести state из процесса (предпосылка масштабирования)
Сейчас `uploads/`, Playwright-сессии и `.env`/`tool.config.json` привязаны к одному процессу. Для горизонтального масштабирования:
- conversation state уже на OpenAI — это плюс;
- `uploads/` → объектное хранилище (S3-совместимое) или, как минимум, вынести директорию за пределы репозитория через env `UPLOAD_DIR`;
- Playwright-сессии (computer use) → отдельный сервис «browser farm», доступный по gRPC/HTTP, с `ComputerSessionManager`-адаптером (протоколы уже готовы — реализация не затронет `routers/chat.py`);
- конфигурацию (`.env`/`tool.config.json`) закешировать в памяти с инвалидацией по mtime (см. §2.2).

### P1-3. Вынести стриминговую state-machine из `routers/chat.py`
Разбить `iterate_stream` на модуль `utils/stream_handler.py` с чистой функцией-редьюсером:
```python
class StreamState:  # заменить неиспользуемый ResponseStreamState
    pending_fns: dict[str, asyncio.Task]
    pending_computer: dict[str, Coroutine]
    result_call_ids: dict[str, str]
    has_approval: bool
    item_id: str
```
Обработчик каждого типа события — отдельная функция; таблица соответствия `event.type → handler`. Это даст: тестируемость каждого перехода, отсутствие 500-строчного `match`, упрощение добавления новых инструментов.

### P1-4. Цикл вместо рекурсии при рестарте потока
Заменить рекурсивный `iterate_stream(next_stream, response_id)` на `while`-цикл с ограничением итераций (например, 10) и явным `break`. Исключает глубокую вложенность при длинных цепочках tool-вызовов и открывает путь к лимиту round-trip'ов (защита от стоимости).

### P1-5. Управление жизненным циклом Playwright-сессий
Добавить TTL/idle-timeout в `BrowserSessionManager` (`last_used` + фоновый `asyncio.Task`-сборщик) и закрытие сессии после `ResponseCompleted` с `endStream`. Текущее поведение (сессии живут до shutdown) — утечка ресурсов при долго работающем сервере.

### P1-6. Вынести `download_container_file` из гонки `base_url`
Создавать отдельный `AsyncOpenAI(base_url=f"https://api.openai.com/v1/containers/{container_id}")` на запрос (или использовать `httpx` напрямую), а не мутировать общий клиент. Устраняет гонку и упрощает тесты.

## 2. Оптимизация производительности

### P2-1. Кэш конфигурации и реестра
`stream_response` на каждое SSE-соединение делает `load_dotenv`, повторный импорт модулей функций и чтение `tool.config.json`. Кэшировать на модульном уровне с инвалидацией по `mtime` (один `stat` вместо полного чтения и пере-импорта):
```python
_cache: dict[str, tuple[float, ToolConfig]] = {}
def load_tool_config() -> ToolConfig:
    mtime = os.path.getmtime(TOOL_CONFIG_PATH)
    if _cache and _cache[0] == mtime: return _cache[1]
    ...
```
Функции импортировать один раз и хранить `ToolRegistration` в кэше.

### P2-2. SSE heartbeat
Добавить периодический `: ping`-комментарий (каждые 15 с) в `event_generator` через `asyncio.wait_for`/`timeout` или фоновую задачу. Предотвращает обрыв соединения через nginx/Cloudflare и упрощает отладку «зависших» потоков.

### P2-3. Уменьшить N+1 в списке файлов
`get_files_for_vector_store` делает `files.retrieve` на каждый файл. Альтернативы: (а) параллельные `gather` уже есть, но добавить `asyncio.Semaphore` для ограничения; (б) кэшировать `filename` локально после первого retrieve (фильтр `modified > last_check`); (в) при больших списках — фоновая синхронизация имени файла.

### P2-4. Стриминг вместо байтов в память
`download_container_file` и `get_assistant_image_content` буферизуют весь файл. Использовать асинхронный чанкинг (например, `file_content.iter_bytes()`/`iter_raw()`), если SDK позволяет, или presigned-редирект. Особенно критично для больших файлов code interpreter.

### P2-5. Аудио-транскрибация
Клиент `AsyncOpenAI` в `routers/audio.py` создаётся на каждый вызов — переиспользовать клиент (модульный синглтон с env-перезагрузкой) или инжектировать через `Depends`, как в остальных роутерах.

## 3. Рефакторинг: первоочередные модули

| Приоритет | Файл | Обоснование | Объём |
|---|---|---|---|
| 1 | `routers/chat.py` | God function, вложенные замыкания, смешение обязанностей; блокирует развитие всех остальных фич | Разбить на: `config_builder`, `sse_handlers`, `tool_executor`; п.1-3 roadmap |
| 2 | `routers/setup.py` | `save_app_config` — 4 ветки в одном endpoint; нормализация MCP продублирована | Вынести нормализацию MCP в `utils/config.py`; разбить endpoint на `POST /config/registry`, `/config/web-search`, `/config/image-gen`, `/config/app` |
| 3 | `utils/function_definitions.py` | 543 строки копии FastMCP, из которых используется малая часть | Удалить неиспользуемые ветки structured-output (или задокументировать как «для будущего»); упростить `pre_parse_json` |
| 4 | `utils/streaming.py` + `utils/threads.py` | Мёртвый код | Удалить `threads.py`; `ResponseStreamState` переосмыслить и использовать (см. P1-3) или удалить |
| 5 | `routers/files.py` | Гонка `base_url`, дублирование логики удаления | Общий `delete_file_resources()`; отдельный клиент для container-скачиваний |
| 6 | `main.py` | `messages`-параметр-фикция; перенос логики редиректа в middleware | Убрать параметр; вынести проверку env в lifespan или в middleware (одна точка вместо трёх `load_dotenv`) |

## 4. DX: тесты, CI/CD, локальный запуск

### Тесты
- **Охват** уже сильный (SSE-конвейер, параллельные tools, Playwright-рендер setup). Пробелы:
  - `setup` POST-ветки (`regenerate_registry`, web_search/image_generation config) не покрыты unit-тестами — только рендер GET;
  - `utils/function_definitions.py` не имеет собственных тестов (интроспекция, aliases, forward-refs);
  - `download_container_file` (гонка `base_url`) не покрыта;
  - e2e-сценарий «полный чат: сообщение → tool call → результат → финальный ответ» с реальным моком SDK.
- Отделить **live**-тесты маркером уже сделано (`-m "not live"`); добавить в CI джобу с реальным ключом (cron/schedule, не на каждый push — экономия).
- Заменить часть `MagicMock`-гирлянд на стабы от `openai` (SDK предоставляет `model_construct` для типов событий — уже используется) и ввести общий `fake_response_stream()` в `tests/conftest.py`.

### CI/CD
- В `release.yml` добавить джобу **tests**: `uv run pytest -m "not live"` (сейчас релизы создаются без прогона тестов).
- `release.yml` запускается на каждый push в main — совместить с PR-проверками (`pull_request` workflow: ruff + ty + pytest).
- Добавить `pip-audit`/`uvx audit` в CI для сканирования зависимостей.

### Локальный запуск и инструменты
- В `README.md` зафиксировать команды: `uv run ruff check`, `uv run ty check`, `uv run pytest -m "not live"`, `uv run playwright install chromium` (частая точка отказа при computer use).
- Автоматизировать bootstrap: `make setup` или `uv run python scripts/bootstrap.py` (создание `.env` из `.env.example`, `playwright install chromium`).
- Покрыть е2e-эндпоинты контрактами (openapi.json генерируется FastAPI автоматически; добавить snapshot-тест на публичный API).
- Шаблон `tool.config.json` вынести в `tool.config.example.json` для читаемого диффа и настройки «с нуля».

## 5. Приоритезированная дорожная карта (суммарно)

```
P0 (безопасность/надёжность, 1-2 дня):
  └─ store_file: sanitize filename + тест
P1 (архитектура, 3-5 дней):
  ├─ StreamState + разбиение iterate_stream
  ├─ цикл вместо рекурсии рестарта
  ├─ TTL для Playwright-сессий
  ├─ отдельный клиент для container-скачиваний
  └─ кэш tool.config.json + env
P2 (производительность и DX, 2-3 дня):
  ├─ SSE heartbeat
  ├─ semaphore + кэш имён в списке файлов
  ├─ рефакторинг setup.py (ветки action)
  ├─ CI-джоба pytest + audit
  └─ чистка мёртвого кода (threads.py, streaming.py)
```
