# AGENTS.md — карта шести AI-проектов

Этот файл — навигационный контекст для AI-агентов, которые работают с каталогом
`two-next-docs`. Здесь собрана документация шести разных проектов чат-приложений с
нейросетевыми моделями. Перед ответом на вопрос определите, к какому проекту он
относится, затем читайте документацию внутри соответствующей папки.

## Как пользоваться этим файлом

1. Определите проект по ключевым словам из вопроса.
2. Прочитайте `01_project_structure.md` и `02_architecture.md` выбранного проекта.
3. Для вопросов о конкретном сценарии читайте `03_execution_flow.md`.
4. Для вопросов о качестве, безопасности и известных проблемах читайте
   `04_code_quality.md`.
5. Для планирования улучшений читайте `05_optimization_roadmap.md`.
6. Для вопросов о моделях и AI-интеграции используйте документы `07_*`, `08_*`,
   `09_*`, `10_*` — набор зависит от проекта.
7. Перед изменением исходного кода прочитайте локальный файл инструкций проекта:
   `AGENTS.ru.md`, `AGENTS_RU.md` или `AGENTS.md`.

Документы в папках — аналитические снимки конкретных репозиториев. Если вопрос
касается фактического поведения кода, приоритет имеют исходный код и локальные
инструкции проекта, а не общие предположения об используемом фреймворке.

## Быстрый выбор проекта

| Если в вопросе упоминается | Проект |
|---|---|
| GitHub Models, `GITHUB_TOKEN`, FastAPI-Users, JWT/Cookie, SQLite, простой чат | `AI-Chatbot/` |
| Groq, WebSocket `/ws/chat`, стриминг чанков, `GROQ_API_KEY`, in-memory-сессии | `GroqStreamChain/` |
| совет моделей, Stage 1/2/3, Chairman, анонимное ранжирование, OpenRouter | `llm-council-karpathy/` |
| Responses API, `conversation_id`, HTMX, MCP approval, computer use, Vector Store | `openai-responses-python-quickstart/` |
| Quorum, TaskOrchestrator, sub-agents, PostgreSQL/pgvector, WebSocket `/ws` | `Quorum/` |
| RAG, база знаний, BM25, OpenSearch, Qdrant, citations, WHMCS, ingestion | `rag-knowledge-base-chatbot/` |

Если вопрос сравнивает несколько подходов, не выбирайте один проект молча:
сопоставьте нужные проекты и явно укажите, где реализована каждая возможность.

---

## 1. `AI-Chatbot/` — простой авторизованный AI-чат

### Назначение

Монолитное SSR-веб-приложение на FastAPI. Пользователь регистрируется и входит в
систему, после чего отправляет запросы одной LLM-модели. Это демонстрационный
одноходовый чат, а не агентная или мультиагентная платформа.

### Технологии и состояние

- Backend: Python 3.13, FastAPI, async SQLAlchemy 2.0, FastAPI-Users.
- Frontend: Jinja2 SSR, Tailwind CSS через CDN, vanilla JavaScript.
- AI: GitHub Models API через `AsyncOpenAI`, OpenAI-compatible Chat Completions.
- Текущая модель: `openai/gpt-4o`.
- База: локальная SQLite через `aiosqlite`; хранится только пользователь.
- Аутентификация: JWT и Cookie backend через FastAPI-Users.
- Чат stateless: история сообщений не сохраняется и не передаётся модели.
- Транспорт: обычный HTTP/JSON; WebSocket и SSE отсутствуют.

### Куда смотреть

- Архитектура: `AI-Chatbot/02_architecture.md`.
- Потоки регистрации, входа и чата: `AI-Chatbot/03_execution_flow.md`.
- AI-интеграция: `AI-Chatbot/08_ai_application_report.md`.
- Модели и провайдеры: `AI-Chatbot/10_models_and_providers.md`.
- Точки входа: `AI-Chatbot/app/main.py`, `AI-Chatbot/app/api/v1/chat.py`.
- Сервис LLM: `AI-Chatbot/app/services/chat.py`.
- Конфигурация: `AI-Chatbot/app/core/config.py`.
- Пользователи и БД: `AI-Chatbot/app/api/v1/users.py`, `AI-Chatbot/app/db/`,
  `AI-Chatbot/app/models/`.

### Важные ограничения

- Вызов LLM, модель, base URL и системный промпт частично зашиты в коде.
- Нет таймаутов и полноценной серверной обработки ошибок LLM.
- В документации зафиксированы риски prompt injection и XSS через `innerHTML`.
- `app/static/` заявлена в `main.py`, но по аналитическому отчёту отсутствует и
  может приводить к падению при запуске.
- Тестового набора и CI/CD нет.

---

## 2. `GroqStreamChain/` — real-time Groq-чат по WebSocket

### Назначение

Монолитное single-process-приложение для чата в реальном времени. FastAPI держит
WebSocket-соединение, отправляет историю в Groq и пересылает ответ клиенту чанками.
Подходит для демо потоковой генерации, но не для production-нагрузки.

### Технологии и состояние

- Backend: Python, FastAPI, Uvicorn, WebSocket.
- Frontend: Jinja2, vanilla JavaScript, CSS.
- AI: нативный Groq SDK; фактический runtime-путь не использует OpenAI SDK.
- Провайдер: Groq Cloud API, ключ `GROQ_API_KEY`.
- Модель: задаётся через `MODEL_NAME`.
- Транспорт: WebSocket `/ws/chat`; ответы идут событиями `stream`.
- История: `ChatSession.messages` в памяти процесса.
- БД, Redis, очередь, постоянное хранилище и мониторинг отсутствуют.

### Куда смотреть

- Архитектура: `GroqStreamChain/02_architecture.md`.
- Жизненный цикл WebSocket и стриминга: `GroqStreamChain/03_execution_flow.md`.
- AI-модели и формат событий: `GroqStreamChain/07_ai_models_report.md`.
- Сервер и маршруты: `GroqStreamChain/server.py`.
- Конфигурация и параметры генерации: `GroqStreamChain/config.py`.
- LLM-сервис: `GroqStreamChain/services/llm_service.py`.
- Модели сессий: `GroqStreamChain/models/chat.py`.

### Важные ограничения

- Настоящий runtime использует `Groq(...)`; инициализированный `ChatGroq` не
  вызывается и считается мёртвым кодом.
- Сессии теряются при рестарте, отключившиеся сессии могут оставаться в памяти.
- В `generate_response_stream()` системный промпт вставляется в исходный список
  сообщений и может накапливаться повторно на каждом ходе.
- Аутентификации, rate limiting и graceful shutdown нет.
- Не реализованы RAG, файлы, tool calling и мультиагентность.

---

## 3. `llm-council-karpathy/` — совет нескольких LLM

### Назначение

Локальное приложение «совет из моделей». Один вопрос проходит три стадии:
несколько моделей отвечают, затем анонимно рецензируют ответы друг друга, после
чего Chairman синтезирует единый результат. Это мультимодельный pipeline с
простой формой кооперации, а не полноценные автономные агенты.

### Технологии и состояние

- Backend: Python 3.10, FastAPI, async `httpx`.
- Frontend: React 19, Vite.
- AI: OpenRouter Chat Completions API.
- Хранение: один JSON-файл на диалог в `data/conversations/`.
- Транспорт: REST + SSE; backend обычно на `8001`, frontend на `5173`.
- Стадии: Stage 1 ответы → Stage 2 анонимные рейтинги → Stage 3 Chairman.
- Внутри Stage 1 и Stage 2 запросы к моделям идут параллельно через
  `asyncio.gather()`.

### Куда смотреть

- Архитектура и data flow: `llm-council-karpathy/02_architecture.md`.
- Сценарии и SSE-события: `llm-council-karpathy/03_execution_flow.md`.
- Подробный AI-отчёт и примеры: `llm-council-karpathy/07_ai_report.md`.
- Оркестратор: `llm-council-karpathy/backend/council.py`.
- OpenRouter-клиент: `llm-council-karpathy/backend/openrouter.py`.
- Конфигурация моделей: `llm-council-karpathy/backend/config.py`.
- Хранилище: `llm-council-karpathy/backend/storage.py`.
- React-обработка событий: `llm-council-karpathy/frontend/src/App.jsx` и `api.js`.

### Важные контракты и ограничения

- Stage 2 получает ответы только как `Response A`, `Response B` и т. п.; имена
  моделей раскрываются только на клиенте.
- Рейтинг ожидает секцию `FINAL RANKING:` и формат `1. Response A`.
- `label_to_model` и `aggregate_rankings` выдаются через SSE, но не сохраняются
  в JSON; после перезагрузки страницы деанонимизация теряется.
- Состав совета и Chairman задаются в `backend/config.py`; модель заголовка
  захардкожена отдельно в `council.py`.
- Все три стадии выполняются последовательно; итеративных раундов и tools нет.
- Интерфейс описан как single-turn, даже если JSON-хранилище содержит историю.

---

## 4. `openai-responses-python-quickstart/` — чат на OpenAI Responses API

### Назначение

Монолитный FastAPI-шаблон, выступающий посредником между браузером и OpenAI
Responses API. Это самый насыщенный инструментами проект среди локальных
чат-шаблонов: файлы, file search, code interpreter, custom functions, MCP,
web search, computer use и image generation.

### Технологии и состояние

- Backend: Python 3.13, FastAPI, Jinja2, HTMX.
- AI: официальный `AsyncOpenAI`, Responses API и Conversations API.
- Frontend: серверные HTML-шаблоны, HTMX, SSE, кастомный JS-рендер Markdown.
- Транспорт: SSE с state machine обработки событий Responses API.
- Состояние диалога хранится на стороне OpenAI; сервер передаёт `conversation_id`.
- Локальная конфигурация: `.env` и `tool.config.json`.
- Файлы: OpenAI Files/Vector Stores плюс локальная копия `uploads/`.
- Computer use: headless Playwright Chromium.

### Куда смотреть

- Архитектура и state machine: `openai-responses-python-quickstart/02_architecture.md`.
- Жизненный цикл, tools, MCP, файлы и аудио: `openai-responses-python-quickstart/03_execution_flow.md`.
- AI-возможности и провайдер: `openai-responses-python-quickstart/07_ai_models_report.md`.
- Главный поток: `openai-responses-python-quickstart/routers/chat.py`.
- Конфигурация: `openai-responses-python-quickstart/utils/config.py` и
  `openai-responses-python-quickstart/routers/setup.py`.
- Реестр функций: `openai-responses-python-quickstart/utils/function_calling.py`.
- Computer use: `openai-responses-python-quickstart/utils/computer_use.py`.
- Тесты: `openai-responses-python-quickstart/tests/`.

### Важные ограничения

- Поддерживается один ассистент с глобальной конфигурацией, полноценной
  мультиагентности нет.
- Прямой провайдер — OpenAI; другой endpoint потребует совместимости с Responses
  API или адаптации state machine.
- Function-вызовы выполняются параллельно, computer-use-вызовы — строго
  последовательно из-за риска гонок браузера.
- Output items записываются в OpenAI conversation по одному, а не батчем.
- `utils/threads.py` — legacy Assistants API и нерабочий код; не использовать как
  основу нового решения.
- Live-тесты требуют реального API-ключа; обычный запуск тестов должен исключать
  live-тесты, если задача не требует внешнего API.

---

## 5. `Quorum/` — мультиагентная платформа

### Назначение

NoOversight/Quorum — наиболее развитая мультиагентная система в наборе. Main Agent
анализирует задачу и решает, делегировать ли её sub-agents. Затем агенты проводят
до трёх раундов обсуждения, а Main Agent синтезирует финальный ответ.

### Технологии и состояние

- Backend: Python 3.13+, FastAPI, asyncio, LangChain/OpenRouter.
- Frontend: React 18, TypeScript, Vite, Zustand, Tailwind.
- LLM: OpenRouter; embeddings — OpenAI.
- Основной транспорт: WebSocket `/ws`; fallback — SSE `/api/task/stream`.
- Персистентность: PostgreSQL + pgvector.
- Инфраструктура: Redis опционально, structured logging, token tracking.
- Tools: web search через DuckDuckGo, Tavily или SerpAPI.
- Оркестратор: `backend/src/core/orchestrator/task_orchestrator.py`.

### Куда смотреть

- Структура и зависимости: `Quorum/01_project_structure.md`.
- Архитектура, БД, состояние и data flow: `Quorum/02_architecture.md`.
- Жизненный цикл, WS-протокол и API: `Quorum/03_execution_flow.md`.
- Мультиагентные возможности: `Quorum/09_capabilities_multiagent.md`.
- AI-модели и роли: `Quorum/07_ai_models_report.md`.
- Main Agent и sub-agents: `Quorum/backend/src/agents/` и
  `Quorum/backend/src/core/orchestrator/`.
- WebSocket API: `Quorum/backend/src/api/routes/websocket.py`.
- Frontend event sourcing: `Quorum/frontend/src/store/slices/streamSlice.ts`.

### Важные ограничения

- Хотя предусмотрено параллельное выполнение, в текущем WebSocket-пути sub-agents
  внутри раунда работают последовательно; `_execute_sub_agents()` не является
  фактическим рабочим путём.
- Tool schemas передаются модели, но полноценное исполнение tool calling в
  `BaseAgent`/оркестраторе не завершено.
- Нет аутентификации и rate limiting в актуальном описании; публично разворачивать
  без соответствующей доработки нельзя.
- Token usage хранится в памяти и теряется при рестарте.
- Часть README/ARCHITECTURE может быть устаревшей; для анализа предпочитать
  `Quorum/01`–`Quorum/05` и исходный код.
- Для изменений backend соблюдайте async-архитектуру, repository/service layers,
  DI и единый обработчик WS-событий во frontend.

---

## 6. `rag-knowledge-base-chatbot/` — корпоративный RAG Support AI

### Назначение

Enterprise RAG-платформа для поддержки клиентов. Система ищет подтверждения в
базе знаний, строит ответ с цитатами и при недостатке данных задаёт уточняющий
вопрос или эскалирует запрос. Поддерживает документы, сайты, WHMCS-тикеты,
админ-панель и stateless suggested replies для внешних helpdesk-систем.

### Технологии и состояние

- Backend: FastAPI, async Python, SQLAlchemy, Celery.
- Frontend: React 19, Vite, админ-панель.
- LLM: `LLMGateway` с OpenAI и OpenAI-compatible endpoint.
- Основной пайплайн: Normalizer → RETRIEVE → ASSESS → DECIDE → GENERATE → VERIFY.
- Поиск: BM25 в OpenSearch + vector search в Qdrant + RRF + reranker.
- Данные: PostgreSQL; raw-файлы могут храниться в MinIO/S3.
- Кэш и очередь: Redis и Celery.
- Ответы имеют citations, confidence и решения `DONE`, `ASK_USER`, `ESCALATE`.

### Куда смотреть

- Структура и сервисы: `rag-knowledge-base-chatbot/01_project_structure.md`.
- Архитектура RAG и ingestion: `rag-knowledge-base-chatbot/02_architecture.md`.
- Execution flow, API и middleware: `rag-knowledge-base-chatbot/03_execution_flow.md`.
- AI-архитектура, модели и JSON-контракты:
  `rag-knowledge-base-chatbot/07_ai_models_report.md`.
- Примеры AI-кода: `rag-knowledge-base-chatbot/08_ai_code_examples.md`.
- Точка входа RAG: `rag-knowledge-base-chatbot/app/services/answer_service.py`.
- Машина состояний: `rag-knowledge-base-chatbot/app/services/orchestrator.py`.
- Поиск: `rag-knowledge-base-chatbot/app/search/`.
- Асинхронный ingestion: `rag-knowledge-base-chatbot/worker/tasks.py`.

### Важные особенности и ограничения

- В одном запросе может выполняться до нескольких специализированных LLM-ролей:
  normalizer, evidence evaluator, generator, self-critic, reviewer и другие.
- LLM-выводы должны соответствовать JSON-контрактам и проходят санитизацию кодом.
- API-stream — псевдострим: pipeline сначала полностью выполняется, затем готовый
  ответ отдаётся SSE-чанками; native token streaming LLM не используется.
- Нативного tool/function calling и автономных агентов нет, но `POST
  /v1/reply/generate` можно использовать как инструмент для внешнего оркестратора.
- Основные зависимости для локального полного стека: PostgreSQL, Redis, OpenSearch,
  Qdrant, MinIO и Celery; часть функций может работать в degraded mode.
- При недоступности retrieval/Redis/reranker предусмотрена ступенчатая деградация,
  но результат нужно интерпретировать с учётом confidence и decision.

---

## Сравнение проектов по ключевым возможностям

| Проект | Один LLM-запрос | Стриминг | Мульти-модельность | RAG | Tools | Постоянное состояние |
|---|---:|---:|---:|---:|---:|---:|
| `AI-Chatbot` | Да | Нет | Нет | Нет | Нет | SQLite только для users |
| `GroqStreamChain` | Да | WebSocket | Нет | Нет | Нет | Нет, только RAM |
| `llm-council-karpathy` | Нет, несколько стадий | SSE-прогресс | Да, Council | Нет | Нет | JSON-файлы |
| `openai-responses-python-quickstart` | Один ассистент | SSE | Нет | File Search | Да, 7 типов | OpenAI Conversations |
| `Quorum` | Несколько ролей/агентов | WebSocket + SSE | Да | pgvector для диалогов | Web search, интеграция tools незавершена | PostgreSQL |
| `rag-knowledge-base-chatbot` | Несколько ролей пайплайна | SSE-псевдострим | Мультиролевой pipeline | Да, основной фокус | Native tool calling нет | PostgreSQL + индексы |

## Как отвечать на вопросы по всем проектам

- Не смешивайте одинаковые термины: `Quorum` — активный мультиагентный
  оркестратор, `llm-council-karpathy` — совет моделей с тремя стадиями,
  `rag-knowledge-base-chatbot` — мультиролевой RAG-пайплайн.
- Для вопроса «где изменить модель» используйте соответственно:
  - `AI-Chatbot/app/services/chat.py`;
  - `GroqStreamChain/.env` и `config.py` (`MODEL_NAME`);
  - `llm-council-karpathy/backend/config.py`;
  - `openai-responses-python-quickstart/.env` или `/setup`;
  - `Quorum/backend/src/agents/agent_factory.py` и настройки;
  - `rag-knowledge-base-chatbot` — env/БД/Admin API через `llm_config.py` и
    `model_router.py`.
- Для вопроса «где хранится история» уточняйте scope: RAM, JSON, OpenAI
  Conversations или PostgreSQL — он различается в каждом проекте.
- Для вопроса «есть ли агенты» отвечайте с градациями: простой single-model чат,
  мультимодельный совет, один ассистент с tools, мультиагентный Quorum или
  мультиролевой RAG pipeline.
- API-ключи и содержимое `.env` не читаются и не выводятся в ответы. Указывайте
  только имена переменных и безопасные пути конфигурации.
- Не утверждайте, что документация описывает актуальный runtime, если в ней явно
  отмечены мёртвый код, заявленные, но отсутствующие файлы, или устаревшие README.
  В таких случаях разделяйте «заявлено» и «фактически используется».

## Общие правила для изменений

- Сначала изучите документацию выбранного проекта, затем конкретный исходный файл.
- Делайте минимальные изменения и сохраняйте существующую архитектуру.
- При изменении API, схемы, событий, формата хранения или AI-контрактов обновляйте
  все места вызова и соответствующую документацию проекта.
- Не логируйте API-ключи, токены, пароли и полный чувствительный пользовательский
  ввод.
- После изменений запускайте доступные проектные проверки из локального
  `AGENTS*`/`README*`.
- Не выполняйте `git commit`, `git push`, `git reset`, `git rebase` и другие
  git-мутации без явного указания пользователя.
