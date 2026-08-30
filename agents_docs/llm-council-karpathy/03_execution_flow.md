# 03 — Логика и работа кода (Execution Flow)

## Жизненный цикл приложения

### Инициализация и запуск
1. Пользователь создаёт `.env` с `OPENROUTER_API_KEY` (см. `README.md`).
2. Запуск через `start.sh` либо вручную двумя процессами:
   - `uv run python -m backend.main` → при импорте `backend/config.py` срабатывает `load_dotenv()`; модуль `backend/main.py` создаёт `app = FastAPI(title="LLM Council API")`, регистрирует CORS-middleware и роуты; `uvicorn.run(app, host="0.0.0.0", port=8001)`.
   - `cd frontend && npm run dev` → Vite dev-server на `http://localhost:5173`.
3. Фронтенд при монтировании (`useEffect` в `App.jsx`) вызывает `api.listConversations()`; `storage.list_conversations()` создаёт директорию `data/conversations/` (через `ensure_data_dir()`), если её нет.
4. Хранилище инициализируется «лениво» — директория и файлы создаются при первой операции записи. Приложение стартует даже без валидного API-ключа (ошибки всплывут только при запросе к моделям).

### Нормальная эксплуатация
- Создание диалога → отправка сообщений → просмотр истории. Сервер не поддерживает сессии/подключения, кроме длительных HTTP-запросов (SSE).

### Завершение работы
- Приложение не выполняет действий при выключении: нет хуков `lifespan`, нет закрытия клиентов, нет graceful shutdown. Незавершённый поток SSE при остановке uvicorn обрывается; уже записанные части диалога сохраняются в JSON (состояние «user-сообщение без ответа» остаётся).
- `start.sh` обрабатывает SIGINT/SIGTERM и убивает оба PID-процесса.

## Ключевые бизнес-процессы (step-by-step)

### Процесс A. Создание диалога
1. `Sidebar.jsx` → кнопка «+ New Conversation» → `App.handleNewConversation()`.
2. `POST /api/conversations` (тело `{}` — пустой Pydantic-модели `CreateConversationRequest` требуется JSON, иначе 422).
3. `backend/main.py`: `uuid.uuid4()` → `storage.create_conversation(id)` → запись `{id, created_at, title: "New Conversation", messages: []}` в `data/conversations/{id}.json`.
4. Ответ `Conversation` добавляется в список `conversations` (без поля `title` — фронтенд опирается на дефолт) и становится текущим.

### Процесс B. Отправка сообщения (основной путь, SSE)
Детально описан в `02_architecture.md` (§ Data Flow). Ключевые подпроцессы:

**B1. Генерация заголовка (только для первого сообщения)**
- В стриминговом пути заголовок считается в фоне: `asyncio.create_task(generate_conversation_title(content))`.
- `generate_conversation_title()`: промпт «3–5 слов» → жёстко `google/gemini-2.5-flash`, таймаут 30 c → чистка кавычек, обрезка до 50 символов. При ошибке — `"New Conversation"`.
- В не-стриминговом пути (`send_message`) заголовок считается **синхронно до** запуска совета — добавляет лишнюю латентность (≈1 LLM-вызов).

**B2. Stage 1 — индивидуальные ответы**
- `stage1_collect_responses(user_query)`: сообщение `{"role": "user"}` → `query_models_parallel(COUNCIL_MODELS)` (4 параллельных запроса).
- Успешные ответы превращаются в `[{"model": ..., "response": ...}]`; сбойные (`None`) отбрасываются.
- Если **все** модели упали → `stage1_results == []`.

**B3. Stage 2 — анонимное рецензирование**
- Метки `Response A/B/C…` по порядку ответов (`chr(65 + i)`); маппинг `label_to_model`.
- Промпт содержит вопрос + анонимизированные ответы + строгий формат: сначала оценка каждого ответа, затем блок `FINAL RANKING:` с нумерованным списком вида `1. Response C`.
- Все модели совета рецензируют параллельно; результат: `[{"model", "ranking", "parsed_ranking"}]`.
- `parse_ranking_from_text()`: ищет `FINAL RANKING:`, извлекает паттерном `\d+\.\s*Response [A-Z]`, иначе fallback — все `Response [A-Z]` подряд, иначе пустой список.
- **Edge case (риск)**: если Stage 1 вернул пустой список, стриминговый путь всё равно запускает Stage 2 с пустым набором ответов — модели получат некорректный промпт. В не-стриминговом пути пустой Stage 1 перехватывается в `run_full_council()`.

**B4. Агрегация рейтингов**
- `calculate_aggregate_rankings(stage2_results, label_to_model)`: для каждой рецензии заново парсит текст ранжирования, для каждой метки из `label_to_model` накапливает позицию; средняя позиция → `{model, average_rank, rankings_count}`, сортировка по возрастанию (лучше — меньше). Модели без упоминаний в рецензиях не попадают в список.

**B5. Stage 3 — синтез председателя**
- `stage3_synthesize_final()`: промпт с исходным вопросом, полными ответами стадий 1–2 **с явными именами моделей** (для председателя анонимность не нужна) и инструкцией «синтезировать коллективную мудрость».
- `query_model(CHAIRMAN_MODEL)` — одиночный запрос. Сбой → fallback `{"response": "Error: Unable to generate final synthesis."}` (при этом статус HTTP остаётся 200).

**B6. Персистентность и завершение**
- `storage.add_assistant_message()` пишет `{role: "assistant", stage1, stage2, stage3}` в JSON-файл. **Метаданные не сохраняются.**
- SSE-события: `stage1_start/complete`, `stage2_start/complete` (+metadata), `stage3_start/complete`, `title_complete`, `complete`.
- Любое исключение внутри генератора → SSE `{type: "error", message}`; статус HTTP уже установлен (200), поэтому клиент узнаёт об ошибке только через событие.

### Процесс C. Не-стриминговый путь (`POST /api/conversations/{id}/message`)
- Аналог процесса B, но: заголовок считается до совета; результат возвращается одним JSON-объектом `{stage1, stage2, stage3, metadata}`; на фронтенде **не используется** (`api.sendMessage()` — мёртвый код).
- Исключение (например, необработанная ошибка) → 500; при этом user-сообщение уже записано в файл — остаётся «битый» диалог.

### Процесс D. Просмотр истории
- `GET /api/conversations` → `list_conversations()`: читает **все** JSON-файлы, возвращает только `{id, created_at, title, message_count}`, сортирует по `created_at` (строковое сравнение ISO, reverse).
- `GET /api/conversations/{id}` → полный диалог или 404.
- На фронтенде метаданные рецензий недоступны (не персистятся), поэтому `Stage2` после reload показывает `Response A/B/C` без жирных имён моделей и без «Street Cred».

## Роутинг и middleware

### Роуты (`backend/main.py`)

| Метод | Путь | Функция | Возвращает |
|---|---|---|---|
| GET | `/` | `root()` | Health-check `{status: "ok", service}` |
| GET | `/api/conversations` | `list_conversations()` | `List[ConversationMetadata]` |
| POST | `/api/conversations` | `create_conversation()` | `Conversation` |
| GET | `/api/conversations/{conversation_id}` | `get_conversation()` | `Conversation` или 404 |
| POST | `/api/conversations/{conversation_id}/message` | `send_message()` | `{stage1, stage2, stage3, metadata}` |
| POST | `/api/conversations/{conversation_id}/message/stream` | `send_message_stream()` | `StreamingResponse` (SSE) |

- Валидация входных данных — только Pydantic-модели (непустота `content` не проверяется; длин лимитов нет).
- `conversation_id` принимается как строка из пути и напрямую конкатенируется в путь файла — см. замечание по безопасности в `04_code_quality.md`.

### Middleware
- Единственный middleware — `CORSMiddleware` (разрешает `localhost:5173` и `localhost:3000`).
- Таймингов, логирования запросов, аутентификации, rate-limiting, gzip — нет. SSE-путь — «ручной»: генератор, `StreamingResponse` с заголовками `Cache-Control: no-cache`, `Connection: keep-alive`.

## Обработка ошибок и логирование

### Стратегия ошибок
1. **Уровень HTTP-клиента** (`openrouter.py`): `try/except Exception` вокруг всего запроса → `print()` + возврат `None`. Исключения не пробрасываются, поэтому `asyncio.gather()` в `query_models_parallel` не может упасть (все таски «безопасные»).
2. **Уровень оркестрации** (`council.py`): фильтрация `None` (Stage 1), текстовый fallback (Stage 3), дефолтный заголовок (title).
3. **Уровень HTTP-слоя** (`main.py`):
   - не-стриминг: HTTPException 404 (нет диалога), необработанные ошибки — 500;
   - стриминг: `try/except` внутри генератора → SSE `error`-событие.
4. **Хранилище** (`storage.py`): `ValueError` при отсутствии диалога в `add_*`-функциях; отсутствующий файл → `None` в `get_conversation`.

### Критические пробелы
- **Нет структурированного логирования**: единственное место логирования — `print()` в `openrouter.py`; ошибки стадий 2/3 и title не логируются вовсе; нет логов запросов, таймингов, статусов моделей.
- **Нет retry/backoff**: одиночный таймаут (120 c) без повторных попыток; кратковременный сбой OpenRouter обнуляет ответ модели.
- **Потерянные данные**: клиентский обрыв SSE после `add_user_message` оставляет user-сообщение без ответа; `create_task` для заголовка может быть не awaits (если генератор прервётся) → «Task was destroyed but it is pending».
- **Неатомарные записи**: `json.dump` напрямую в целевой файл — при сбое в момент записи файл повреждается (нет temp+rename).
- **Ошибки не структурированы**: в SSE `error` передаётся голый `str(e)`; клиент лишь пишет его в `console.error`.
