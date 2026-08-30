# 02 — Архитектура и паттерны

## Высокоуровневая архитектура

Система — **двухкомпонентный слоистый монолит** (SPA + автономный HTTP-бэкенд), без микросервисов, очередей и БД:

1. **Фронтенд** (`frontend/`) — React SPA, обслуживается Vite dev-server на порту 5173. Содержит только представление и состояние UI. Вся «тяжёлая» работа выполняется бэкендом.
2. **Бэкенд** (`backend/`) — FastAPI-приложение на порту 8001, запускаемое как модуль (`python -m backend.main`). Внутри разделён на четыре слоя:
   - **HTTP-слой** — `backend/main.py` (роуты, CORS, SSE);
   - **Слой приложения / оркестрации** — `backend/council.py` (бизнес-процесс из 3 стадий);
   - **Слой внешних интеграций** — `backend/openrouter.py` (адаптер к OpenRouter);
   - **Слой хранения** — `backend/storage.py` (JSON-файлы).

Зависимости направлены сверху вниз: `main.py` → `council.py` → `openrouter.py` / `storage.py`. Обратные зависимости отсутствуют; связность между модулями — через явный импорт констант из `backend/config.py`.

```
┌──────────────────────────────┐
│  Браузер (React SPA, :5173)  │
│  App.jsx → api.js → SSE-клиент│
└──────────────┬───────────────┘
               │ HTTP (REST + SSE), CORS: localhost:5173/3000
┌──────────────▼───────────────┐
│  FastAPI (backend/main.py)   │  HTTP-слой
│  роуты /api/conversations*   │
└──────┬──────────────┬────────┘
       │              │
┌──────▼──────┐ ┌─────▼───────┐
│ council.py  │ │ storage.py  │  слой приложения / хранения
│ 3 стадии    │ │ JSON-файлы  │
└──────┬──────┘ └─────────────┘
       │
┌──────▼──────────────┐
│ openrouter.py       │  слой интеграций
│ httpx.AsyncClient   │
└──────┬──────────────┘
       │ HTTPS
┌──────▼──────────────┐
│ OpenRouter API      │  внешний сервис
│ (Chat Completions)  │
└─────────────────────┘
```

## Используемые паттерны проектирования

| Паттерн | Где применяется | Комментарий |
|---|---|---|
| **Adapter / Facade** | `backend/openrouter.py` | Единая функция `query_model(model, messages)` скрывает разницу между вендорами (OpenAI, Google, Anthropic, xAI) за стандартным интерфейсом `{content, reasoning_details}` |
| **Orchestrator** | `run_full_council()` в `backend/council.py` | Центральная функция, последовательно координирующая три стадии и собирающая результат `(stage1, stage2, stage3, metadata)` |
| **Dependency Injection (вручную)** | `backend/storage.py`, `backend/council.py` | Функции получают входные данные параметрами; глобальные зависимости (API-ключ, модели) подтягиваются импортом констант из `config.py`. Полноценного DI-контейнера нет |
| **Anonymization (контекстный анти-bias)** | `stage2_collect_rankings()` | Ответы маскируются под `Response A/B/C…`, создаётся обратный маппинг `label_to_model`; деанонимизация выполняется на клиенте только для отображения |
| **Fallback / graceful degradation** | `query_model()`, `stage3_synthesize_final()`, `generate_conversation_title()` | Сбой одной модели не роняет весь запрос: `None` отфильтровывается, председатель имеет текстовый fallback, заголовок — `"New Conversation"` |
| **Optimistic UI** | `App.jsx` (`handleSendMessage`) | Пользовательское сообщение и заглушка ответа добавляются в состояние до ответа сервера, затем обновляются по SSE-событиям |
| **Repository (упрощённый)** | `backend/storage.py` | Слой, изолирующий детали хранения (файлы/JSON) от остального кода; интерфейс — набор функций, а не класс |
| **Template Method (на уровне промптов)** | `stage1/2/3` в `council.py` | Стабильный каркас «собери промпт → вызови модели → нормализуй результат» с разными телами промптов |

## Поток данных (Data Flow)

Полный цикл запроса (используется приложение, включая стриминг):

```
1. Пользователь вводит вопрос в ChatInterface.jsx (textarea)
2. App.handleSendMessage():
   ├── optimistic: user message + assistant-заглушка в state
   └── api.sendMessageStream() → POST /api/conversations/{id}/message/stream
3. backend/main.py:
   ├── проверка существования диалога (storage.get_conversation)
   ├── создание async-генератора событий
   └── StreamingResponse(media_type="text/event-stream")
4. Генератор (по шагам):
   ├── storage.add_user_message()                     → JSON-файл
   ├── (для 1-го сообщения) asyncio.create_task(generate_conversation_title)
   ├── SSE "stage1_start" → stage1_collect_responses()
   │        └── query_models_parallel(COUNCIL_MODELS)
   │              └── asyncio.gather(4× query_model)   → OpenRouter API
   ├── SSE "stage1_complete" (данные стадии)
   ├── SSE "stage2_start"  → stage2_collect_rankings()
   │        ├── анонимизация ответов (Response A/B/C…)
   │        ├── query_models_parallel(COUNCIL_MODELS)  → OpenRouter API
   │        └── parse_ranking_from_text() для каждой рецензии
   ├── calculate_aggregate_rankings()                  → средние позиции
   ├── SSE "stage2_complete" (+ metadata: label_to_model, aggregate_rankings)
   ├── SSE "stage3_start"  → stage3_synthesize_final() → query_model(CHAIRMAN_MODEL)
   ├── SSE "stage3_complete"
   ├── await title_task → storage.update_conversation_title()
   ├── SSE "title_complete"
   ├── storage.add_assistant_message(stage1, stage2, stage3) → JSON-файл
   └── SSE "complete"
5. api.js парсит SSE-события → onEvent(type, payload)
6. App.jsx обновляет state последнего assistant-сообщения (stage1/stage2/stage3)
7. ChatInterface.jsx рендерит Stage1.jsx / Stage2.jsx / Stage3.jsx
```

Временные ограничения: стадии строго последовательны (stage2 зависит от результатов stage1, stage3 — от stage2), но **внутри** каждой стадии все модели опрашиваются параллельно; генерация заголовка в стриминговом пути запускается в фоне параллельно стадиям. Латентность запроса ≈ сумма латентностей трёх стадий, где каждая стадия ограничена самой медленной моделью.

**Чтение истории диалога** (reload страницы): `GET /api/conversations/{id}` → `storage.get_conversation()` → JSON-файл → `messages[]`. Метаданные (`label_to_model`, `aggregate_rankings`) **не персистятся** — после перезагрузки страницы рецензии показываются с анонимными метками без деанонимизации и без агрегатного рейтинга.

## Состояние, кэширование, конфигурация

### Состояние
- **Серверная часть — stateless**: единственное состояние — JSON-файлы диалогов на диске. Каждый HTTP-запрос независим; сессий, мемкэшей и глобального кэша нет.
- **Клиентская часть**: состояние полностью в React (`useState` в `App.jsx` и компонентах). При перезагрузке страницы состояние восстанавливается из бэкенда через REST.
- Модели **не получают контекст предыдущих сообщений** диалога: каждая стадия использует только текущий вопрос — дизайн «одного хода» (single-turn). Бэкенд при этом хранит историю, создавая расхождение возможностей (см. `04_code_quality.md`).

### Кэширование
Отсутствует полностью. Каждый запрос повторно генерирует заголовок, прогоняет все три стадии и заново читает/пишет JSON-файлы. Единственный кэш-подобный механизм — optimistic-обновления в UI до прихода SSE.

### Конфигурация
- **Секреты**: `OPENROUTER_API_KEY` — переменная окружения, загружается `python-dotenv` из `.env` при импорте `backend/config.py` (`load_dotenv()` на уровне модуля).
- **Модели и константы**: жёстко зашиты в `backend/config.py` (`COUNCIL_MODELS`, `CHAIRMAN_MODEL`). Изменение состава совета требует правки кода и рестарта.
- **Исключение из конвенции**: генератор заголовков жёстко использует `google/gemini-2.5-flash` прямо в `council.py` (не из `config.py`) — риск дрейфа конфигурации.
- **Фронтенд**: адрес бэкенда захардкожен как `http://localhost:8001` в `frontend/src/api.js`; окружения для разных API-баз нет.
- **Сетевые параметры**: таймаут по умолчанию 120 c (`query_model`), для заголовка — 30 c.

### CORS
`allow_origins = ["http://localhost:5173", "http://localhost:3000"]`, `allow_credentials=True`, методы и заголовки разрешены любые. Работает только для локальной разработки; при выносе бэкенда на другой хост/порт потребует правки.
