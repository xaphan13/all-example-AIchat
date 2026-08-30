# AGENTS.md — Контекст проекта для AI-агентов

Универсальный файл для любых AI-харнесов (Claude Code, Codex CLI, Cursor, Aider, OpenCode, Amp и др.).
Спецификация: https://agents.md

## Обзор

**LLM Council** — локальное веб-приложение «совета из LLM». Пользователь задаёт вопрос, несколько моделей отвечают параллельно (Stage 1), анонимно рецензируют и ранжируют друг друга (Stage 2), после чего председатель (Chairman) синтезирует единый финальный ответ (Stage 3). Ключевая идея — анонимизация ответов на этапе рецензирования, чтобы модели не «играли в фаворитов».

Стек: Python 3.10 / FastAPI + async httpx (бэкенд), React 19 + Vite (фронтенд), JSON-файлы (хранилище), uv (Python), npm (JS). Внешний сервис — только OpenRouter API. БД и брокеров нет.

## Быстрый старт

```bash
# 1. Зависимости
uv sync                       # бэкенд
cd frontend && npm install    # фронтенд

# 2. Ключ API (обязателен для реальной работы)
# создай .env в корне: OPENROUTER_API_KEY=sk-or-v1-...

# 3. Запуск
./start.sh                    # или вручную:
uv run python -m backend.main # бэкенд, порт 8001
cd frontend && npm run dev    # фронтенд, порт 5173
```

## Структура репозитория

```
backend/
  config.py       # Модели совета, председатель, API-ключ, пути (хардкод-конфиг)
  main.py         # FastAPI: роуты, CORS, SSE-стриминг (порт 8001)
  openrouter.py   # HTTP-клиент OpenRouter: query_model(), query_models_parallel()
  council.py      # Оркестрация 3 стадий, парсинг рейтингов, агрегация
  storage.py      # JSON-хранилище диалогов в data/conversations/
frontend/src/
  App.jsx         # Оркестрация UI + обработка всех SSE-событий + optimistic UI
  api.js          # fetch-клиент + ручной парсер SSE
  components/
    Sidebar.jsx       # Список диалогов
    ChatInterface.jsx # Лента сообщений + форма ввода (single-turn)
    Stage1.jsx        # Вкладки индивидуальных ответов
    Stage2.jsx        # Рецензии + деанонимизация на клиенте + «Street Cred»
    Stage3.jsx        # Финальный ответ председателя
docs/               # Полная техническая документация (01–05)
data/conversations/ # Диалоги (JSON), создаётся автоматически
```

## Архитектура и поток данных

Зависимости сверху вниз: `main.py` → `council.py` → `openrouter.py` / `storage.py`. Все LLM-вызовы идут через OpenRouter Chat Completions API.

```
POST /api/conversations/{id}/message/stream  (SSE)
  stage1_start → stage1_collect_responses()  → asyncio.gather по всем моделям
  stage1_complete
  stage2_start → stage2_collect_rankings()   → анонимизация (Response A/B/C) + параллельные рецензии
  stage2_complete (+ metadata: label_to_model, aggregate_rankings)
  stage3_start → stage3_synthesize_final()   → одиночный вызов председателя
  stage3_complete → title_complete → complete
  error (при любом исключении)
```

Стадии строго последовательны; внутри стадии модели опрашиваются параллельно. Заголовок диалога генерируется фоновой задачей (`google/gemini-2.5-flash`) только для первого сообщения.

**Важные контракты:**
- Ответы бэкенда: `{content, reasoning_details?}`; сбой модели → `None` (graceful degradation, запрос не роняем).
- Рецензия обязана содержать секцию `FINAL RANKING:` с нумерованным списком `1. Response A` — парсится regex'ом в `parse_ranking_from_text()`.
- Assistant-сообщение в JSON: `{role, stage1, stage2, stage3}`; **метаданные (`label_to_model`, `aggregate_rankings`) не персистятся** — после reload страницы рецензии теряют деанонимизацию.

## Ключевые конвенции и подводные камни

1. **Запуск бэкенда строго как** `python -m backend.main` из корня проекта (относительные импорты `from .config import ...`). Запуск из директории `backend/` сломает импорты.
2. **Порты**: бэкенд 8001, фронтенд 5173. При смене обновлять `backend/main.py` (uvicorn + CORS) **и** `frontend/src/api.js` (`API_BASE`).
3. **Модели и председатель** — захардкожены в `backend/config.py` (`COUNCIL_MODELS`, `CHAIRMAN_MODEL`). Модель заголовков захардкожена в `council.py` (не в конфиге).
4. **UI single-turn**: форма ввода в `ChatInterface.jsx` рендерится только при пустом списке сообщений — после первого вопроса ввод исчезает (бэкенд историю хранит, но мультитурн в UI не реализован).
5. **Все ReactMarkdown** оборачивать в `<div className="markdown-content">` (глобальный стиль в `index.css`).
6. **Деанонимизация на клиенте**: модели получают только метки `Response X`; имена подставляются жирным в `Stage2.jsx` исключительно для отображения.
7. **Валидация**: `content` не проверяется на пустоту; `conversation_id` конкатенируется в путь файла без валидации — при доработке хранилища экранировать `..`.
8. **Стиль кода**: функциональные модули с docstring'ами и аннотациями типов, без классов (исключений нет). Следовать существующему стилю, не менять без необходимости.

## Документация

**Не обходи проект целиком для понимания архитектуры** — вместо этого начни с папки `docs/` (полная актуальная документация, сгенерированная по коду):

- `docs/01_project_structure.md` — карта проекта: дерево, ответственность каждого модуля, внешние зависимости
- `docs/02_architecture.md` — архитектура и паттерны: слои, схема Data Flow, состояние/конфигурация/CORS
- `docs/03_execution_flow.md` — жизненный цикл, бизнес-процессы, роутинг, обработка ошибок
- `docs/04_code_quality.md` — технический долг, code smells, безопасность и надёжность
- `docs/05_optimization_roadmap.md` — приоритеты развития и рефакторинга (P0–P2)

Прочие файлы: `README.ru.md` / `CLAUDE.ru.md` — русские версии `README.md` / `CLAUDE.md`; `AGENTS.md` — английская версия этого файла.
