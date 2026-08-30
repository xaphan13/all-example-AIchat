# 05 — Предложения по развитию (Optimization Roadmap)

## 1. Архитектурные улучшения

### 1.1. Внешнее хранилище состояния (Приоритет: критичный)

**Проблема:** `chat_sessions` и `active_connections` (`server.py:33,36`) хранятся in-memory. Рестарт процесса теряет все сессии, несколько инстансов не могут разделять состояние, память растёт без ограничений.

**Решение:**
- Заменить in-memory dict на **Redis** (рекомендуется) с TTL для сессий: `Redis + JSON-сериализация ChatSession` + `EXPIRE` на 24h. Это даст идемпотентность при scale-out и сохранит историю при рестарте.
- Абстрагировать хранилище за интерфейсом `ChatSessionStore` (Repository Pattern), чтобы менять backend (dict → Redis → Postgres) без правки `server.py`.

**Файлы:** `server.py:33`, новый `services/session_store.py`.

### 1.2. Аутентификация и rate limiting (Приоритет: критичный)

**Проблема:** `/ws/chat` доступен без аутентификации; нет ограничения на количество соединений и частоту сообщений — вектор DoS.

**Решение:**
- Добавить JWT или query-token аутентификацию: `ws://host/ws/chat?token=...`, проверка через FastAPI dependency.
- Rate limiting: `slowapi`/`limits` или in-house счётчик на Redis (`INCR` + `EXPIRE`) по IP/пользователю (например, N запросов / 10 сек).
- Ограничить число одновременных WebSocket-соединений на клиента (модульный счётчик в `ConnectionManager`).

**Файлы:** `server.py`, новый `services/auth.py`.

### 1.3. Асинхронная обработка (Приоритет: высокий)

**Проблема:** `services/llm_service.py:72-86` — синхронный Groq-стрим в `asyncio.to_thread` + синхронная итерация `for chunk in completion` блокирует thread из пула на всё время генерации. Параллелизм ограничен размером thread pool.

**Решение:**
- Перейти на **асинхронный Groq SDK**: `groq.AsyncGroq` + `async for chunk in await client.chat.completions.create(...)`. Это убирает thread pool из горячего пути и масштабируется event-loop'ом.
- `AsyncGroq` использует `httpx.AsyncClient` — реализовать пул клиентов и закрытие в lifespan.

**Файлы:** `services/llm_service.py`.

### 1.4. Graceful shutdown и масштабируемый deployment (Приоритет: высокий)

**Проблема:** нет обработки жизненного цикла (`lifespan`), `reload=True` в `server.py:149`.

**Решение:**
- Использовать FastAPI `lifespan`-контекст: инициализация/закрытие клиентов, flush сессий при остановке, `ws_disconnect` для всех активных соединений при SIGTERM.
- Вынести `uvicorn.run(... reload=True)` за пределы production-кода; оставить `python -m uvicorn server:app` для prod.
- Документировать запуск за reverse-proxy (nginx/Caddy) для TLS (`wss://`).

**Файлы:** `server.py:148-149`.

### 1.5. Межпроцессная координация (Приоритет: средний)

При запуске нескольких worker'ов (`--workers 4`) клиент может переподключиться к другому инстансу и потерять сессию (если нет общего хранилища). Решение — п. 1.1 (Redis) + sticky routing (nginx `ip_hash`).

---

## 2. Оптимизация производительности

| # | Участок | Проблема | Оптимизация | Ожидаемый эффект |
|---|---|---|---|---|
| 1 | `services/llm_service.py:72-86` | Thread-blocking стриминг | `groq.AsyncGroq` + `async for` | Параллелизм растёт с N-соединений до десятков-сотен без расширения pool'а. |
| 2 | `server.py:113` — `full_response += chunk` | Конкатенация строк O(n²) | Накопление в `list[str]` + `''.join()` | Ускорение на больших ответах (маловлиятельно на практике, но дешёво). |
| 3 | `services/llm_service.py:62` — `messages.insert(0, ...)` | Мутация списка сессии на каждый вызов; контекст засоряется дубликатами system-промпта | Строить полный список локально: `[system] + converted` без мутации | Экономия токенов, стабильность context window, меньше стоимость. |
| 4 | `server.py` — глобальные dict'ы | O(1) lookup, но нет eviction | TTL/максимальный размер сессий; очистка при `disconnect()` | Контроль потребления памяти (устранение memory leak). |
| 5 | LLM-запрос | Отправляется вся история сессии | Ограничить контекст: отправлять последние N сообщений или слайдинг-окно по токенам | Уменьшение latency и token cost на длинных сессиях. |
| 6 | `static/js/main.js` — `innerHTML` пересборка | `appendToAssistantMessage()` переписывает весь `innerHTML` на каждый чанк | Инкрементальное добавление текстовых узлов; markdown-рендер в фоне | Меньше reflow/repaint, плавность стрима на длинных ответах. |
| 7 | Groq-вызовы | Нет кэширования | Кэш идентичных запросов (заглушка) или batch-prefill | Снижение стоимости для повторяющихся промптов (вторично). |

---

## 3. Рефакторинг (приоритизированный список)

### P0 — баги и безопасность (исправить в первую очередь)

| Файл | Изменение | Обоснование |
|---|---|---|
| `services/llm_service.py:62` | Убрать мутацию `messages.insert(0, ...)`; строить локальный список с system-промптом | Критический баг: дубликаты system-промпта в истории, некорректное поведение LLM, переполнение контекста. |
| `static/js/main.js:135,151-154` | Заменить `innerHTML` на `textContent` + безопасный markdown-парсер (например, `marked` с `sanitize`), либо DOMPurify | XSS-уязвимость: LLM-контент может содержать произвольные теги/скрипты. |
| `server.py:133-140` | Удалять сессию из `chat_sessions` при disconnect; не полагаться на `if 'session_id' in locals()` | Memory leak при длительной работе. |
| `server.py:36` | Удалить дублирующий модульный `active_connections` | Мёртвый код. |
| `services/llm_service.py:18-33` | Удалить `ChatGroq` и `_convert_to_langchain_messages()` либо начать их использовать | Мёртвый код / двойной клиент; расход при инициализации. |
| `config.py` | Добавить валидацию `GROQ_API_KEY`/`MODEL_NAME` на старте (raise early с понятным сообщением) | Ошибка сейчас проявляется в runtime при первом запросе. |
| `server.py:88-90` | Обработать `json.JSONDecodeError` от клиента | Падение соединения при некорректном payload. |

### P1 — архитектурная чистка

| Файл | Изменение | Обоснование |
|---|---|---|
| `server.py:65-140` | Разбить `websocket_endpoint()` на отдельные обработчики: `_handle_message()`, `_handle_stream()`, `_handle_disconnect()` | God function, снижение тестируемости. |
| `models/chat.py:15-16` | Удалить `ChatRequest` (не используется) или применить для REST-альтернативы | Мёртвый код. |
| `services/llm_service.py` | Ввести интерфейс `LLMProvider` (abc) + реализация `GroqLLMProvider`; инъекция через конструктор | DIP: возможность замены провайдера, лёгкий мок в тестах. |
| `requirements.txt` | Удалить `sqlalchemy`, `requests` (если не планируются) | Мёртвые зависимости. |
| `pyproject.toml` | Синхронизировать с `requirements.txt`, указать версию Python консистентно (README vs pyproject vs .python-version) | Конфликт метаданных Python 3.9/3.13. |
| `config.py` | Перейти на Pydantic Settings (`pydantic-settings`) | Валидация типов, defaults, `env_file` — единый источник конфигурации. |

### P2 — DX и процесс

| Файл | Изменение | Обоснование |
|---|---|---|
| `services/llm_service.py:93`, `server.py:137` | Узкие `except` (исключения Groq SDK, JSON), кастомные типы ошибок | Broad catch маскирует реальные причины. |
| Логирование | Structured logging (JSON), lazy-логирование (`logger.info("...%s", arg)`) | Трассируемость, производительность. |
| `system_prompts.py` | Перенести промпт в отдельный файл (`prompts/system.md`) | Удобство редактирования. |

---

## 4. Рекомендации по DX (Developer Experience)

### 4.1. Тесты

**Текущее состояние:** только ручной скрипт `test_groq.py`. Не является pytest-тестом, не проверяет логику сервера.

**Рекомендуемые тесты:**
- **Unit-тесты (`pytest` + `pytest-asyncio`):**
  - `LLMService._convert_to_groq_messages()` — конвертация моделей, наличие system-промпта ровно один раз.
  - `ConnectionManager.connect()/disconnect()` — регистрация/очистка соединений.
  - WebSocket-handler: mock `LLMService`, проверка последовательности сообщений (`session_id` → `initial_message` → `message_received` → `stream*` → `stream_end`) через `TestClient`/`AsyncClient` из `starlette`.
- **Integration-тест:** один тест с `VCR`/mock Groq API для проверки сквозного стриминга.
- **Frontend-тесты:** `Vitest` для `handleSocketMessage()` (порядок типов сообщений, состояние UI).

### 4.2. CI/CD

```yaml
# .github/workflows/ci.yml — эскиз
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.13" }
      - run: pip install -r requirements.txt
      - run: pip install pytest pytest-asyncio
      - run: pytest tests/ -v
      # Опционально: ruff check . && ruff format --check .
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: pip install ruff
      - run: ruff check .
```

Дополнительно: `pre-commit` хуки (ruff, mypy), dependabot для `requirements.txt`.

### 4.3. Локальный запуск

- Создать **`.env.example`** с шаблоном (`GROQ_API_KEY=`, `MODEL_NAME=llama-3.1-8b-instant`).
- Добавить `Makefile`/`Taskfile` или скрипты:
  - `make install` — `pip install -r requirements.txt`
  - `make run` — `uvicorn server:app --reload`
  - `make test` — `pytest tests/`
- Документировать запуск в Docker: добавить `Dockerfile` + `docker-compose.yml` (сервис + Redis для п. 1.1).
- Добавить `ruff`/`mypy` конфиг в `pyproject.toml` (сейчас секция `[project]` пустая, без tooling-конфигурации).

### 4.4. Мониторинг

- Добавить структурированные метрики (prometheus-client): число активных WebSocket, длительность LLM-вызовов, ошибки Groq.
- `/health` расширить до deep-check: доступность Groq API (лёгкий ping) и состояние хранилища.

---

## Приоритизация

| Приоритет | Работы | Обоснование |
|---|---|---|
| **P0 (критично, сейчас)** | Мутация system-промпта, XSS, memory leak, удаление мёртвого кода | Прямые баги и уязвимости, влияют на корректность/безопасность. |
| **P1 (в этом квартале)** | AsyncGroq, Redis-хранилище, аутентификация + rate limiting, lifespan, разбиение `websocket_endpoint()`, Pydantic Settings | Масштабируемость и надёжность. |
| **P2 (постоянно)** | Тесты, CI/CD, linting, structured logging, Docker, .env.example | Качество кодовой базы и скорость разработки. |
