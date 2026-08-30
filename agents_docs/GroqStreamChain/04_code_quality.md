# 04 — Оценка качества кодовой базы

## Общая оценка

| Критерий | Оценка | Комментарий |
|---|---|---|
| Читаемость | ★★★★☆ | Код чистый, хорошо структурирован, понятные имена, осмысленные комментарии. |
| Модульность | ★★★☆☆ | Базовое разделение на models/services/server, но нет слоёв data-access и config-validation. |
| Связность (cohesion) | ★★★☆☆ | Модули связаны разумно, но `server.py` совмещает роутинг, управление состоянием и оркестрацию. |
| Зацепление (coupling) | ★★☆☆☆ | `server.py` напрямую мутирует `chat_sessions` dict; `LLMService` мутирует входящий список сообщений. |
| Идиоматичность Python | ★★★★☆ | Async/await, type hints, Pydantic — используются правильно. Но `asyncio.to_thread` для синхронного стрима — workaround. |
| Тестируемость | ★★☆☆☆ | Нет unit-тестов. `test_groq.py` — ручной скрипт, не pytest. Зависимости не инъектируются. |
| Безопасность | ★★☆☆☆ | Нет аутентификации, валидации ввода, XSS-уязвимость на клиенте. |

---

## Соответствие принципам SOLID, DRY, KISS

### SOLID

| Принцип | Статус | Детали |
|---|---|---|
| **S** — Single Responsibility | ⚠ Частично | `server.py` отвечает за роутинг, управление соединениями, хранение состояния и оркестрацию LLM-вызовов. `LLMService` — корректно изолирован. |
| **O** — Open/Closed | ✘ Нарушен | Добавление нового типа сообщений или нового LLM-провайдера требует модификации существующих классов. Нет интерфейсов/абстракций. |
| **L** — Liskov Substitution | N/A | Нет иерархии наследования. |
| **I** — Interface Segregation | ✘ Нарушен | `LLMService` содержит `_convert_to_langchain_messages()` (не используется), `_convert_to_groq_messages()`, `generate_response_stream()` — нет разделения интерфейсов. |
| **D** — Dependency Inversion | ✘ Нарушен | `server.py` напрямую зависит от конкретного `LLMService` (создаёт экземпляр на уровне модуля). Нет абстракции `LLMProviderInterface`. |

### DRY

| Нарушение | Где | Описание |
|---|---|---|
| Дублирование `active_connections` | `server.py:36` (модульный dict) и `server.py:46` (`ConnectionManager.active_connections`) | Мёртвая переменная на уровне модуля, дублирующая менеджер. |
| Двойная инициализация клиентов | `services/llm_service.py:17-23` | Создаются `Groq` и `ChatGroq` — второй никогда не используется. |

### KISS

Проект в целом следует KISS — простая архитектура, минимум абстракций. Однако простота достигнута ценой production-готовности: in-memory хранилище, отсутствие аутентификации, нет retry-логики для LLM-вызовов.

---

## Технический долг и запахи кода (Code Smells)

### Критические баги

| # | Проблема | Файл:строка | Влияние |
|---|---|---|---|
| 1 | **Мутация списка сообщений сессии** — `messages.insert(0, system_message)` добавляет системный промпт в `chat_sessions[session_id].messages` при **каждом** вызове. Список растёт бесконечно, контекст LLM засоряется дубликатами системного промпта. | `services/llm_service.py:62` | Некорректные ответы LLM, рост token-usage и стоимости, потенциальное превышение context window. |
| 2 | **Утечка памяти** — `chat_sessions[session_id]` не удаляется при отключении. Только `active_connections` очищается. | `server.py:56-59` + `server.py:133-136` | При длительной работе память растёт без ограничений. |
| 3 | **XSS-уязвимость** — `messageElement.innerHTML = content` и `processCodeBlocks()` используют `innerHTML` с непроверенным контентом от LLM/пользователя. | `static/js/main.js:135`, `static/js/main.js:151-154` | Выполнение произвольного JS-кода в браузере пользователя. |

### Мёртвый код (Dead Code)

| # | Элемент | Файл:строка | Описание |
|---|---|---|---|
| 1 | `self.langchain_client = ChatGroq(...)` | `services/llm_service.py:18-23` | Инициализируется, но никогда не вызывается. |
| 2 | `_convert_to_langchain_messages()` | `services/llm_service.py:25-33` | Метод существует, но не вызывается нигде. |
| 3 | `active_connections` (модульная переменная) | `server.py:36` | Дублирует `ConnectionManager.active_connections`, не используется. |
| 4 | `ChatRequest` модель | `models/chat.py:15-16` | Определена, но не используется ни в одном роуте. |
| 5 | `SQLAlchemy` зависимость | `requirements.txt:33` | В requirements, но не импортируется. |
| 6 | `requests` зависимость | `requirements.txt:30` | В requirements, но не импортируется напрямую. |

### Узкие места (Bottlenecks)

| # | Узкое место | Файл:строка | Причина |
|---|---|---|---|
| 1 | `asyncio.to_thread` для стриминга | `services/llm_service.py:72-81` | Синхронный `client.chat.completions.create(stream=True)` обёрнут в `to_thread`. Итерация `for chunk in completion` (строка 86) — **синхронная**, блокирует поток из пула. Один поток на соединение → ограничение по параллелизму = размер thread pool (обычно `min(32, cpu+4)`). |
| 2 | `reload=True` в production | `server.py:149` | Watcher-process расходует CPU на мониторинг файлов. |
| 3 | In-memory `chat_sessions` без eviction | `server.py:33` | Нет TTL, нет лимита на количество сессий или сообщений. |
| 4 | Синхронная конкатенация строк `full_response += response_chunk` | `server.py:113` | O(n²) при больших ответах (Python string immutability). |

### Запахи кода

| # | Smell | Где | Рекомендация |
|---|---|---|---|
| 1 | God Function | `server.py:65-140` — `websocket_endpoint()` (75 строк) | Разбить на `handle_connect()`, `handle_message()`, `handle_disconnect()`. |
| 2 | Broad `except Exception` | `server.py:137`, `services/llm_service.py:93` | Ловить конкретные исключения (`groq.APIError`, `json.JSONDecodeError`). |
| 3 | `if 'session_id' in locals()` | `server.py:135`, `server.py:139` | Антипаттерн — использовать `session_id = None` перед `try`. |
| 4 | f-strings в logging | По всему коду | Использовать `logger.info("msg %s", arg)` для lazy-evaluation. |
| 5 | `isinstance(msg, dict)` в `_convert_to_groq_messages` | `services/llm_service.py:40` | Сигнал о нарушении типизации — смешение `Message` и `dict` в одном списке. |

---

## Оценка безопасности и надёжности

### Безопасность

| Категория | Статус | Детали |
|---|---|---|
| **Аутентификация** | ✘ Отсутствует | Любой клиент может подключиться к `/ws/chat`. Нет токенов, сессий, API-key проверки. |
| **Авторизация** | ✘ Отсутствует | Нет разграничения доступа. |
| **Валидация ввода** | ⚠ Минимальная | `json.loads(data)` без обработки `JSONDecodeError`. `message_data.get("message", "")` — нет проверки длины, формата, содержания. |
| **XSS** | ✘ Уязвимость | `innerHTML` с непроверенным контентом в `static/js/main.js`. |
| **Секреты в коде** | ✅ Нет | `GROQ_API_KEY` берётся из `.env`. Но нет валидации наличия при старте. |
| **CORS** | ✘ Не настроен | Нет `CORSMiddleware`. Приложение не отдаёт CORS-заголовки — frontend должен быть same-origin. |
| **Rate limiting** | ✘ Отсутствует | Один клиент может открыть множество WebSocket и спамить сообщениями. |
| **Transport security** | ✘ Отсутствует | Нет TLS/HTTPS. `ws://` вместо `wss://` (клиент выбирает по `window.location.protocol`). |

### Надёжность

| Категория | Статус | Детали |
|---|---|---|
| **Persistence** | ✘ Отсутствует | Все сессии in-memory. Рестарт = потеря всех данных. |
| **Retry / Resilience** | ✘ Отсутствует | Нет retry-логики для Groq API вызовов (несмотря на `tenacity` в зависимостях). |
| **Graceful shutdown** | ✘ Отсутствует | Нет обработки SIGTERM, нет закрытия активных соединений. |
| **Health check** | ⚠ Базовый | `/health` возвращает `{"status": "ok"}` без проверки доступности Groq API или состояния сессий. |
| **Resource limits** | ✘ Отсутствует | Нет лимита на количество одновременных WebSocket-соединений, длину сообщений, размер истории сессии. |
| **Конфигурация Python** | ⚠ Конфликт | `README.md` → 3.9, `pyproject.toml` → `>=3.13`, `.python-version` → `3.13`. |
