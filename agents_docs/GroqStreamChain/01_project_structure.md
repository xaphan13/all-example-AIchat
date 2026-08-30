# 01 — Карта проекта (Project Structure)

## Назначение проекта

**GroqStreamChain** — это real-time AI-чат-приложение, построенное на FastAPI и WebSocket. Сервер поддерживает постоянное WebSocket-соединение с клиентом, принимает текстовые сообщения, пересылает их в LLM через Groq API и стримит ответ обратно чанками (chunk-by-chunk), обеспечивая низкую воспринимаемую задержку. Интеграция с LangChain присутствует в коде, но фактически не используется в runtime — весь поток ответов идёт через нативный Groq SDK.

Проект представляет собой **монолитное single-process приложение** без внешней БД, брокера сообщений или persistent-хранилища. Состояние сессий хранится in-memory в Python-словарях, что делает систему пригодной для демо/прототипа, но не для production-нагрузок.

---

## Дерево директорий и ключевых файлов

```
GroqStreamChain/
├── server.py                  # Точка входа. FastAPI-приложение, WebSocket-эндпоинт /ws/chat, ConnectionManager, in-memory хранилище сессий.
├── config.py                  # Загрузка .env, конфигурация LLM (temperature, max_tokens, top_p) и сервера (HOST, PORT).
├── system_prompts.py          # Единственная константа SYSTEM_PROMPT — системный промпт для LLM.
├── test_groq.py               # Standalone-скрипт для ручной проверки доступности Groq API (не pytest-тест).
├── requirements.txt           # Pin-список зависимостей (41 пакет, включая неиспользуемые SQLAlchemy, requests).
├── pyproject.toml             # Минимальный uv/pyproject-конфиг. dependencies пуст, requires-python >=3.13.
├── .python-version            # Фиксирует Python 3.13 (для uv/pyenv).
├── .gitignore                 # Игнорирует .env, .venv, __pycache__, IDE-файлы.
├── README.md                  # Документация для пользователей: badges, инструкции запуска, описание фич.
├── LICENSE                    # MIT License, Copyright (c) 2025 Promila Ghosh.
│
├── models/
│   └── chat.py                # Pydantic-модели: Message (role, content), ChatSession (id, messages), ChatRequest (message, session_id).
│
├── services/
│   └── llm_service.py         # LLMService: инициализирует Groq-клиент и ChatGroq (LangChain), метод generate_response_stream() — async-генератор стриминга чанков.
│
├── templates/
│   └── index.html             # Jinja2-шаблон: HTML-разметка чат-UI, подключает /static/css/style.css и /static/js/main.js.
│
├── static/
│   ├── css/
│   │   └── style.css          # Стили чат-интерфейса: layout, bubble-сообщения, typing-indicator, code-block.
│   ├── js/
│   │   └── main.js            # Клиентская логика: WebSocket-подключение, reconnect с exponential backoff, обработка stream-чанков, typing-indicator, отправка сообщений.
│   ├── groqstreamchain.gif    # Демо-гиф для README.
│   └── groqstreamchain.png    # Статичный скриншот.
│
└── .venv/                     # Виртуальное окружение (не в git).
```

---

## Внешние зависимости и их роль

### Runtime-зависимости (из `requirements.txt`)

| Зависимость | Версия | Роль в проекте |
|---|---|---|
| `fastapi` | 0.115.12 | Веб-фреймворк: HTTP-роутинг (`/`, `/health`), WebSocket-эндпоинт (`/ws/chat`), static-files mount. |
| `uvicorn` | 0.34.2 | ASGI-сервер для запуска FastAPI. Используется с `reload=True` в `server.py`. |
| `websockets` | 15.0.1 | Низкоуровневая WebSocket-библиотека (транзитивная зависимость FastAPI/uvicorn). |
| `groq` | 0.24.0 | Нативный Groq SDK. **Фактически используется** для стриминга LLM-ответов в `services/llm_service.py`. |
| `langchain` | 0.3.25 | Фреймворк оркестрации LLM. Импортируются `HumanMessage`, `AIMessage`, но **не вызываются** в runtime. |
| `langchain-groq` | 0.3.2 | Интеграция LangChain ↔ Groq. `ChatGroq` инициализируется в `LLMService.__init__`, но **не используется** для генерации. |
| `langchain-core` | 0.3.58 | Ядро LangChain (транзитивная зависимость). |
| `langchain-text-splitters` | 0.3.8 | Текстовые сплиттеры LangChain (транзитивная, не используется). |
| `langsmith` | 0.3.42 | Телеметрия/трейсинг LangChain (транзитивная, не используется). |
| `pydantic` | 2.11.4 | Валидация данных: модели в `models/chat.py`. |
| `python-dotenv` | 1.1.0 | Загрузка `.env` в `config.py`. |
| `jinja2` | 3.1.6 | Шаблонизация HTML-страницы (`templates/index.html`). |
| `sqlalchemy` | 2.0.40 | ORM. **Присутствует в requirements, но нигде не импортируется и не используется.** |
| `requests` | 2.32.3 | HTTP-клиент. **Присутствует в requirements, но не используется напрямую.** |
| `httpx` | 0.28.1 | Async HTTP-клиент (транзитивная зависимость Groq/LangChain). |
| `tenacity` | 9.1.2 | Библиотека retry-логики (транзитивная зависимость LangChain). |
| `orjson` | 3.10.18 | Быстрый JSON-сериализатор (транзитивная зависимость FastAPI). |
| Остальные (`annotated-types`, `anyio`, `certifi`, `charset-normalizer`, `click`, `distro`, `h11`, `httpcore`, `idna`, `jsonpatch`, `jsonpointer`, `markupsafe`, `packaging`, `pydantic_core`, `pyyaml`, `requests-toolbelt`, `sniffio`, `starlette`, `typing-inspection`, `typing_extensions`, `urllib3`, `zstandard`) | — | Транзитивные зависимости вышеперечисленных пакетов. |

### Внешние сервисы / API

| Сервис | Роль |
|---|---|
| **Groq Cloud API** (`https://api.groq.com`) | Единственный внешний API. Принимает chat-completion-запросы со стримингом. Требует `GROQ_API_KEY`. Модель задаётся через `MODEL_NAME` (по умолчанию `llama-3.1-8b-instant`). |

### Отсутствующие инфраструктурные компоненты

- **База данных:** отсутствует. Состояние сессий — in-memory `dict` в `server.py:33` (`chat_sessions`) и `server.py:36` (`active_connections`).
- **Брокер сообщений / очередь:** отсутствует.
- **Кэш (Redis и т.п.):** отсутствует.
- **Система мониторинга / лог-агрегатор:** отсутствует (только `logging.basicConfig` в stdout).
- **CI/CD:** отсутствует.
