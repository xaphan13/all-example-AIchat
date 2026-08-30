# 04. Оценка качества кодовой базы (Code Quality Review)

> Оценка дана для версии проекта 1.4.14 (см. `pyproject.toml`). Масштаб: ~2800 строк Python, ~17 Jinja-шаблонов, ~1000 строк кастомного JS.

## 1. Читаемость и стиль

**Сильные стороны:**
- Проект проходит `ruff check` (дефолтный набор правил + намеренный `BLE001`) и `ty check` (type checker) — статическая гигиена поддерживается автоматически через Stop-hook в `.claude/hooks/lint-and-typecheck.sh`.
- Согласованные современные идиомы Python 3.13: `match`/`case`, `Annotated[...]` для FastAPI-параметров, дженерики `FunctionResult[T]`, `str | None` вместо `Optional`, keyword-only параметры с `default_factory`.
- Докстринги у большинства функций и модулей; комментарии объясняют *почему* (например, workaround для bug в Responses API при MCP approval, почему `client.base_url` меняется вручную).
- Тесты читабельны: доменные хелперы (`make_single_function_stream()`, `build_mock_client()`) скрывают низкоуровневую возню с моками.

**Слабые стороны:**
- `routers/chat.py` (779 строк) — один файл с двумя монолитными функциями (`stream_response`, `iterate_stream`) и вложенными замыканиями (`run_function`, `run_computer`); индексация кода затруднена, вложенность достигает 5-6 уровней.
- Именование переменных «простыни»: `ws_tool`, `ig_tool`, `all_item_ids`, `result_call_ids` — без контекста не очевидно.
- Jinja-шаблоны содержат inline-стили (registry-row, mcp-row) — верстка рассредоточена между `styles.css` и атрибутами `style=`.
- Остатки легаси/мусора: `utils/threads.py` (мёртвый код Assistants API), `utils/streaming.py:ResponseStreamState` (не используется), `main.py:95-96` — TODO о thread-менеджменте.

## 2. Модульность, связность (cohesion) и связанность (coupling)

| Аспект | Оценка |
|---|---|
| Разделение HTTP/serвис | Хорошее: `routers/*` не содержат бизнес-логики инструментов; `utils/*` не знают о FastAPI (исключение: `utils/files.py` возвращает `FileResponse`/`HTTPException` — сервисный слой связан с веб-фреймворком). |
| Связность `utils/function_definitions.py` | Высокая (543 строки одной темы: интроспекция типов → Pydantic), но это скопированный код FastMCP — внутренне избыточен (4 фабрики моделей), из которых в проекте реально используются ~30% (аргументные модели и `pre_parse_json`; structured-output ветки не задействованы: `ToolRegistry.call` игнорирует `return_structured`). |
| Связность `routers/chat.py` | Низкая когезия обязанностей: и сборка конфигурации, и рендер шаблонов, и state-machine событий, и оркестрация tool-задач, и формирование SSE — в одном потоке функции. |
| Циклические зависимости | Отсутствуют (`utils` → SDK; `routers/chat` → `routers/files` только для `url_path_for`). |
| Сквозные сущности | `ToolTaskResult` вводится как связующий DTO между функциями и stream — разумно. |

## 3. Соответствие принципам

- **SOLID**
  - S: нарушается в `routers/chat.py` (см. выше), в `routers/setup.py` (`save_app_config` — 4 действия в одном endpoint) и в `utils/files.py` (и работа с ФС, и HTTP-ответы).
  - O/C: `ToolRegistry` открыт для расширения; протоколы computer use — образцовая открытость к подмене бэкенда.
  - L: иерархия `Tool*Error` корректна; `BrowserSessionManager` реализует `ComputerSessionManager` контрактно.
  - I: протоколы сессий минимальны (3-4 метода) — хорошо.
  - D: нарушений нет; клиент OpenAI инжектится через `Depends`.
- **DRY**: умеренно. Дублируются: нормализация `require_approval` (setup.py дважды: `read_setup` и `save_app_config`), JSON-чтение `tool.config.json` (`read_registry_entries`/`read_mcp_servers` почти идентичны), три `except`-блока валидации `tool.config.json` в `stream_response`, схожие паттерны удаления файлов (`delete_file` vs `delete_all_files`).
- **KISS**: обратная сторона — избыточная защита в отдельных местах (пред-парсинг JSON в `function_definitions.py:pre_parse_json` с комментарием про «Claude desktop», structured-output фабрики — неиспользуемый оверхеад).
- **YAGNI**: `ResponseStreamState`, `utils/threads.py`, structured-output ветки — явные кандидаты на удаление.

## 4. Технический долг и «запахи кода»

| # | Запах | Расположение | Комментарий |
|---|---|---|---|
| 1 | **God function** | `routers/chat.py:stream_response` / `iterate_stream` | ~500 строк логики в одной корутине; расширение (новый tool) требует правки гигантского `match`. |
| 2 | **Dead code** | `utils/threads.py`; `utils/streaming.py:ResponseStreamState`; ветки `structured_output` в `function_definitions.py` | Legacy от Assistants API / недописанные абстракции. |
| 3 | **Hidden dependency / runtime import** | `routers/chat.py:149-155` (`import importlib, os` внутри генератора) | Конфигурация и реестр собираются на каждое SSE-соединение; блокирующий `load_dotenv` на горячем пути. |
| 4 | **Общая мутация объекта** | `routers/files.py:download_container_file` (`client.base_url = ...`) | Гонка при конкурентных запросах; правильнее — отдельный `AsyncOpenAI` или низкоуровневый `httpx`. |
| 5 | **Unused parameter / параметр-фикция** | `main.py:read_home(messages=...)`; `FunctionResult` генерики без проверки | `messages` никогда не передаётся; `return_structured` игнорируется в `ToolRegistry.call`. |
| 6 | **Магические строки** | имена инструментов (`"web_search_preview"`, `"image_generation"`, `"computer"`), пути шаблонов, `"assistants"` purpose | Разбросаны по коду и шаблонам; нет единого enum/констант. |
| 7 | **Перехват исключений как flow control** | `routers/setup.py:save_app_config` (весь endpoint в try/except), `chat.py` (3 catch-all вокруг SDK) | BLE001 отключён намеренно («границы деградируют вместо 500»), но гранулярность страдает. |
| 8 | **Хардкод данных** | `routers/setup.py:69-76` (список моделей), `templates/index.html` (CDN `marked`/`dompurify` без SRI), `main.py` (порт 8000) | Модели устаревают, CDN — внешний фактор доступности. |
| 9 | **Несогласованная обработка XSS** | `templates/index.html:13` (`{{ msg.text | safe }}`) vs `static/stream-md.js` (DOMPurify) | Стриминговый контент санитизируется на клиенте, но исторические `messages` рендерятся через `| safe` без санитизации на сервере. |
| 10 | **Debug-логи в проде** | `static/stream-md.js` (`console.log` в каждом обработчике) | Не критично для шаблона, но шумит. |

## 5. Узкие места (bottlenecks)

1. **Один процесс = одно событийное кольцо.** Все SSE-потоки, Playwright-сессии и файловые операции живут в одном процессе; горизонтальное масштабирование невозможно без выноса состояния (conversation state на OpenAI не проблема, но in-memory Playwright-сессии и локальные `uploads/` — проблема).
2. **`get_or_create_vector_store` + `get_files_for_vector_store`** на каждый вызов списка файлов: N+1 запросы (`files.list` → по `files.retrieve` на каждый файл через `gather`).
3. **`download_container_file`** — стриминг через Python (bytes в памяти) вместо редиректа на presigned-URL; плюс гонка `base_url`.
4. **SSE без heartbeat**: промежуточные прокси могут оборвать «молчащее» соединение при долгой генерации (нет `: ping` комментариев).
5. **Рестарт потока рекурсией**: каждая итерация — новый `responses.create`; при длинных цепочках tool-вызовов растёт вложенность корутин (не стек-переполнение, но глубина состояния). Комментарий в коде: рестарт лишь один на итерацию.
6. **`update_env_file`** — блокирующая запись файла без блокировок; конкурентные `/setup`-сохранения могут потерять значения.
7. **Playwright-сессии без TTL** — живут до `close_all()` (shutdown); при длинной работе процесса аккумулируются браузеры.

## 6. Безопасность и надёжность

| Риск | Уровень | Описание |
|---|---|---|
| **Путь-траверсал при upload** | Высокий | `utils/files.py:store_file` пишет по `os.path.join(upload_dir, file_name)` **без проверки**; злонамеренный `filename="..\\evil.txt"` (Windows) или `../evil.txt` может записать файл за пределы `uploads/`. (Проверки есть только в `retrieve_file`/`delete_local_file`, но не при записи.) |
| **Отсутствие аутентификации/авторизации** | Высокий | Любой, кто достучался до порта, может: читать/удалять все файлы, использовать ключ API через `/audio/transcribe` и другие endpoints. Приемлемо для локального шаблона, критично при деплое. |
| **API-ключ в открытом виде** | Средний | `OPENAI_API_KEY` хранится plaintext в `.env` (необходимо для GUI-подхода) и логируется через `logger.debug` в `update_env_file`. |
| **IDOR по `file_id`** | Средний | `GET /files/{file_id}/content` отдаёт произвольный файл по известному id (vision-миниатюры). Без auth — любой файл аккаунта. |
| **Утечка деталей исключений** | Средний | Глобальный handler рендерит `str(exc)` в `error.html`; ошибки SDK попадают в HTML-фрагменты (например, `f"<pre>Error: {e}</pre>"` в `stream_response`). |
| **Мутный `safe` рендер** | Средний | `assistant-step.html` использует `| safe` для `content_html`; содержимое — серверный HTML (контролируемый), но пользовательские строки (`user_input`) вставляются как текст — ок. Основной риск — исторические `messages` (`index.html`). |
| **Чувствительные данные в `tool.config.json`** | Средний | Bearer-токены и заголовки MCP хранятся plaintext в JSON (файл вне `.gitignore`-правил не указан — необходимо проверить). |
| **Гонки в `client.base_url`** | Низкий | См. п.4 (bottlenecks). |
| **Надёжность: event-loop блокировки** | Низкий | Единственный блокирующий I/O в горячем пути (`tool.config.json`) уже вынесен в `asyncio.to_thread`; остальные — async. |
| **Надёжность: восстановление после сбоя** | Средний | Ошибка на середине SSE оставляет разговор в согласованном состоянии (результаты коммитятся в conversation), но клиент получает `networkError` без авто-resume. |

## 7. Итоговые оценки

| Критерий | Оценка (0–5) | Обоснование |
|---|---|---|
| Читаемость | 4.0 | Понятные имена, комментарии-почему; снижают монолит chat.py и шаблонная «простынность» |
| Модульность | 3.5 | Чистое разделение routers/utils; страдает когезия chat.py и дублирование конфиг-слоя |
| Тестируемость | 4.5 | Отличные мок-утилиты, SSE-парсер, Playwright-инфраструктура; ~194 теста |
| Современность идиом | 4.5 | Python 3.13, `match`, `Annotated`, типизация проходит `ty check` |
| Технический долг | 3.0 | Мёртвый код, god function, неиспользуемые абстракции, дублирование |
| Безопасность | 2.5 | Траверсал в `store_file`, нет auth, IDOR, детали исключений в UI |
| Надёжность | 3.5 | Аккуратные catch-all границы, отмена задач, но нет heartbeat/reconnect/backpressure |
