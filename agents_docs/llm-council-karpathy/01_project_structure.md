# 01 — Карта проекта (Project Structure)

## Назначение проекта

**LLM Council** — локальное веб-приложение «совета из LLM», альтернатива стандартному ChatGPT-чату. Вместо обращения к одной модели пользователь задаёт вопрос нескольким LLM через [OpenRouter](https://openrouter.ai/), затем эти модели анонимно рецензируют и ранжируют ответы друг друга (Stage 2), после чего председатель (Chairman) синтезирует единый финальный ответ (Stage 3). Ключевая инновация — **анонимизация ответов на этапе рецензирования**: модели не знают, чьи ответы оценивают, что исключает предвзятость в пользу конкретного вендора.

Стек: **Python 3.10 / FastAPI + async httpx** (бэкенд), **React 19 + Vite** (фронтенд), **JSON-файлы** (хранилище), менеджер проектов **uv**. Проект позиционируется автором как «vibe-coded» прототип выходного дня (см. `README.md`), поэтому код намеренно минимален и не покрыт тестами.

## Дерево проекта

```
llm-council-karpathy/
├── README.md                  # Общее описание, инструкция по запуску, стек
├── CLAUDE.md                  # Технические заметки для агентов/разработчиков (частично устарели)
├── pyproject.toml             # Манифест uv/Python-пакета; зависимости бэкенда
├── uv.lock                    # Зафиксированный снимок зависимостей (uv)
├── .python-version            # Пин версии Python (3.10)
├── .gitignore                 # Исключены: .env, data/, node_modules/, .venv и т.д.
├── .env                       # Секреты; НЕ в git; содержит OPENROUTER_API_KEY
├── header.jpg                 # Картинка для README
├── main.py                    # ЗАГЛУШКА: hello-world из шаблона uv (мёртвый код)
├── start.sh                   # Скрипт одновременного запуска бэкенда и фронтенда
│
├── backend/                   # ── БЭКЕНД (FastAPI, порт 8001) ──────────────
│   ├── __init__.py            # Маркер пакета (пусто)
│   ├── config.py              # Конфигурация: модели совета, председатель, ключ API, пути
│   ├── main.py                # FastAPI-приложение: роуты, CORS, SSE-стриминг
│   ├── openrouter.py          # HTTP-клиент к OpenRouter (адаптер над Chat Completions API)
│   ├── council.py             # Оркестрация 3 стадий + парсинг ранжирований + агрегация
│   └── storage.py             # Персистентность: JSON-файл на диалог
│
├── frontend/                  # ── ФРОНТЕНД (React SPA, Vite, порт 5173) ─────
│   ├── index.html             # Точка входа Vite
│   ├── package.json           # Манифест npm; react, react-dom, react-markdown
│   ├── package-lock.json      # Зафиксированные версии npm-пакетов
│   ├── vite.config.js         # Конфиг Vite (только плагин react)
│   ├── eslint.config.js       # ESLint 9 (flat config) для JS/JSX
│   ├── README.md              # Шаблонный README от create-vite (не актуален)
│   ├── public/vite.svg        # Иконка Vite
│   └── src/
│       ├── main.jsx           # Точка монтирования React (StrictMode)
│       ├── App.jsx            # Оркестрация UI: состояние диалогов, SSE-события, optimistic UI
│       ├── api.js             # Тонкий HTTP-клиент бэкенда + парсер SSE
│       ├── index.css          # Глобальные стили + .markdown-content
│       ├── App.css            # Каркас приложения (flex-раскладка)
│       └── components/
│           ├── Sidebar.jsx/.css       # Список диалогов + кнопка «New Conversation»
│           ├── ChatInterface.jsx/.css # Лента сообщений, индикаторы загрузки стадий, форма ввода
│           ├── Stage1.jsx/.css        # Вкладки с индивидуальными ответами моделей
│           ├── Stage2.jsx/.css        # Вкладки с рецензиями + деанонимизация + агрегатный рейтинг
│           └── Stage3.jsx/.css        # Финальный ответ председателя
│
└── data/conversations/       # Хранилище диалогов (JSON); создаётся автоматически; в git не попадает
```

## Ключевые модули и их ответственность

### Бэкенд (`backend/`)

| Файл | Ответственность | Ключевые абстракции |
|---|---|---|
| `backend/config.py` | Единственный источник конфигурации. При импорте вызывает `load_dotenv()`. Содержит список моделей совета, модель председателя, URL OpenRouter и путь к данным. | Модульные константы (`COUNCIL_MODELS`, `CHAIRMAN_MODEL`, `OPENROUTER_API_KEY`, `OPENROUTER_API_URL`, `DATA_DIR`) |
| `backend/openrouter.py` | Адаптер над OpenRouter Chat Completions API. Инкапсулирует HTTP-вызов, заголовки авторизации и нормализацию ответа в словарь `{content, reasoning_details}`. | `query_model()` — одиночный запрос; `query_models_parallel()` — параллельные запросы через `asyncio.gather()` |
| `backend/council.py` | Ядро бизнес-логики: три стадии совета. Строит промпты, деанонимизирует/анонимизирует ответы, парсит рейтинги и агрегирует их. | `run_full_council()` — оркестратор; `stage1_collect_responses()`, `stage2_collect_rankings()`, `stage3_synthesize_final()`; `parse_ranking_from_text()` (regex); `calculate_aggregate_rankings()`; `generate_conversation_title()` |
| `backend/storage.py` | Слой персистентности без БД: один JSON-файл на диалог в `data/conversations/`. | CRUD-функции диалогов: `create/get/list/save`, `add_user_message()`, `add_assistant_message()`, `update_conversation_title()` |
| `backend/main.py` | HTTP-слой: FastAPI-приложение, CORS, REST-роуты, SSE-стриминг. Связывает `council.py`, `storage.py` и сеть. | Pydantic-модели запросов/ответов; `StreamingResponse` + async-генератор событий |

### Фронтенд (`frontend/src/`)

| Файл | Ответственность |
|---|---|
| `App.jsx` | Владелец глобального состояния: список диалогов, текущий диалог, флаг загрузки. Обрабатывает optimistic-добавление сообщений и все события SSE. |
| `api.js` | Функции `fetch` для всех роутов; `sendMessageStream()` читает `ReadableStream` и диспетчеризует SSE-события через колбэк `onEvent(type, payload)`. |
| `ChatInterface.jsx` | Рендер ленты сообщений, спиннеры стадий, textarea (Enter — отправка, Shift+Enter — перенос строки), автопрокрутка вниз. |
| `Stage1.jsx` | Таб-вью индивидуальных ответов каждой модели (ReactMarkdown). |
| `Stage2.jsx` | Таб-вью «сырых» рецензий; клиентская деанонимизация меток `Response X` → `**имя_модели**`; блок «Extracted Ranking» для валидации парсинга; агрегатный рейтинг «Street Cred». |
| `Stage3.jsx` | Финальный ответ председателя с зелёной подсветкой (`#f0fff0`). |
| `Sidebar.jsx` | Список диалогов с заголовками и счётчиком сообщений, переключение и создание диалогов. |

## Внешние зависимости

| Зависимость | Роль | Примечания |
|---|---|---|
| **OpenRouter Chat Completions API** (`https://openrouter.ai/api/v1/chat/completions`) | Единственный внешний сервис: все LLM-вызовы (стадии 1–3, генерация заголовка) проходят через него | Авторизация по Bearer-токену из `OPENROUTER_API_KEY`; `reasoning_details` извлекаются из ответа, но нигде не используются |
| **Файловая система** (JSON-файлы в `data/conversations/`) | Персистентность диалогов | Не является БД в классическом смысле: чтение/запись целиком, без транзакций и блокировок |
| **Python-пакеты**: `fastapi`, `uvicorn[standard]`, `python-dotenv`, `httpx`, `pydantic` | Каркас бэкенда | Версии зафиксированы в `pyproject.toml` / `uv.lock` |
| **npm-пакеты**: `react` 19, `react-dom`, `react-markdown` 10; dev: `vite` 7, `eslint` 9 | Фронтенд | Версии зафиксированы в `frontend/package-lock.json` |

Базы данных, брокеры сообщений и прочие внешние сервисы **отсутствуют** — всё состояние приложения находится либо в памяти фронтенда, либо в локальных JSON-файлах.
