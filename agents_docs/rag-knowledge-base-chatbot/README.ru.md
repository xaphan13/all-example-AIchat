# Auto Reply Chatbot | Support AI Assistant

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109+-green.svg)](https://fastapi.tiangolo.com)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

[English](README.md) | **Русский**

**RAG-чат-бот** (Retrieval-Augmented Generation) — корпоративный AI-ассистент поддержки. Отвечает на вопросы службы поддержки через REST API с использованием **гибридного поиска** (BM25 + векторный поиск) по вашей базе знаний. Сочетает данные, собранные веб-краулером, вручную подготовленные примеры диалогов и непрерывное обучение на высоко оценённых диалогах.

> 🔍 *Ключевые слова: RAG-чат-бот, LLM-ассистент поддержки, краулер тикетов WHMCS, векторный поиск, AI-база знаний, автоматизация поддержки клиентов*

## Содержание

- [Источники данных и непрерывное обучение](#источники-данных-и-непрерывное-обучение)
- [Возможности](#возможности)
- [Технологический стек](#технологический-стек)
- [Быстрый старт](#быстрый-старт)
- [Руководство по использованию](#руководство-по-использованию)
- [Аутентификация](#аутентификация)
- [API эндпоинты](#api-эндпоинты)
- [Конфигурация](#конфигурация)
- [Структура проекта](#структура-проекта)
- [Документация](#документация)

## Источники данных и непрерывное обучение

База знаний строится из **трёх источников** и **постоянно улучшается** через цикл обратной связи:

### 1. Данные, собранные веб-краулером

- **Тикеты WHMCS**: краулинг тикетов поддержки из WHMCS (через Playwright, вход по cookies или логину/паролю)
- **Документы по URL**: получение содержимого веб-страниц (политики, FAQ, документация) через API `/documents/fetch-from-url`
- **Краулинг сайта**: обход всего сайта через `/documents/crawl-website`
- **Source JSON**: загрузка из различных форматов — `pages` (url, title, text), `articles`, `plans`, `sales_kb` и др.
- **Дамп SQL WHMCS**: импорт тикетов из `source/*.sql` через `make import-whmcs`

### 2. Вручную подготовленные примеры диалогов

- **sample_conversations.json**: добавление качественных примеров диалогов напрямую (реальные вопросы и ответы)
- **sample_docs.json**: заранее подготовленные статические документы (веб-страницы, статьи)
- **custom_docs.json**: документы, созданные из админ-панели, синхронизируются обратно в файл

### 3. Обучение на высоко оценённых диалогах

- Собранные тикеты **вручную проверяются** (одобрить/отклонить). В базу знаний попадают только **одобренные** тикеты
- **Экспорт одобренных тикетов** → `sample_conversations.json` через `POST /v1/admin/ingest-tickets-to-file`
- Повторный запуск ingest, чтобы новые примеры диалогов были эмбеддены и проиндексированы в OpenSearch/Qdrant
- Цикл: *Краулинг → Проверка (одобрение) → Экспорт → Ingestion* позволяет системе **обучаться** на реальных качественных диалогах

---

## Возможности

- **RAG**: BM25 (OpenSearch) + векторный поиск (Qdrant) + реранкинг
- **Диалоги**: CRUD, синхронный/стриминговый чат, привязка к тикету/livechat
- **Тикеты**: список из БД, процесс одобрения (pending/approved/rejected)
- **Документы**: CRUD, загрузка по URL, краулинг сайта, повторный краулинг, загрузка файлов
- **Краулер WHMCS**: краулинг тикетов через Playwright, сохранение cookies, проверка сессии
- **Админ**: ingestion документов/тикетов, конфигурация (промпты, интенты, типы документов, LLM, архитектура), брендинг
- **Авторизация**: JWT-логин, API-токены (sk_*), управление пользователями
- **Frontend**: React + Vite — Логин, Диалоги, Примеры диалогов, Документы, Краулинг, Дашборд, Интенты, Типы документов, Настройки, API-токены, Справочник API

## Технологический стек

- **API**: FastAPI + Pydantic v2 + Uvicorn
- **БД**: PostgreSQL 15+
- **Кэш/очереди**: Redis + Celery
- **Поиск**: OpenSearch (BM25), Qdrant (векторный)
- **Эмбеддинги/LLM**: OpenAI (подключаемый)
- **Краулер**: Playwright (Chromium)
- **Frontend**: React 19, Vite 7, Tailwind CSS

## Быстрый старт

### Предварительные требования

- Docker и docker-compose
- OpenAI API key

### Переменные окружения

```bash
cp .env.example .env
# Отредактируйте .env: OPENAI_API_KEY, JWT_SECRET (production), ADMIN_API_KEY, API_KEY
```

### Запуск с Docker Compose

```bash
docker-compose up -d
```

- **API**: http://localhost:8000
- **Frontend**: http://localhost:5174
- **MinIO**: http://localhost:9000 (консоль: 9001)

**С Nginx-шлюзом** (API на порту 80):

```bash
docker-compose --profile full up -d
```

### Миграции и начальная настройка

```bash
# Внутри контейнера
docker-compose exec api alembic upgrade head
docker-compose exec api python -m scripts.create_admin_user   # Создание админа (после миграции 011)
docker-compose exec api python scripts/ingest_from_source.py
docker-compose exec api python scripts/ingest_tickets_from_source.py

# Или локально (с запущенными сервисами)
make init-db
make create-admin
make ingest
```

**Исходные файлы** в `source/`:

- `sample_docs.json` – документы (pages: url, title, text)
- `sample_conversations.json` – тикеты/диалоги (из краулинга WHMCS или вручную)
- `custom_docs.json` – документы, созданные из админ-панели
- `*.sql` – дампы SQL WHMCS для `make import-whmcs`

Поддерживаемые форматы см. в `app/services/source_loaders.py`.

### Локальная разработка

1. Запустите PostgreSQL, Redis, OpenSearch, Qdrant (или используйте docker-compose только для инфраструктуры)
2. `pip install -r requirements.txt`
3. `uvicorn app.main:app --reload`
4. Worker: `celery -A worker.celery_app worker --loglevel=info`
5. `alembic upgrade head`
6. `make create-admin` (создание первого админа)

## Руководство по использованию

### Первоначальная настройка (полный сценарий)

1. **Запустите сервисы**: `docker-compose up -d`
2. **Выполните миграции**: `docker-compose exec api alembic upgrade head`
3. **Создайте админа**: `docker-compose exec api python -m scripts.create_admin_user` (введите username/password по запросу)
4. **Войдите во frontend**: Откройте http://localhost:5174 → Войдите с только что созданным аккаунтом
5. **Добавьте данные в базу знаний** (выберите один или несколько способов ниже)

### Способ 1: Ingestion из JSON-файлов в `source/`

Подготовьте `source/sample_docs.json` или `source/sample_conversations.json`:

```json
// sample_docs.json - документы (веб-страницы, политики, FAQ)
{
  "pages": [
    {"url": "https://example.com/refund-policy", "title": "Refund Policy", "text": "Полное содержимое..."}
  ]
}

// sample_conversations.json - вопросы и ответы из тикетов (требуются external_id, subject, description)
{
  "source": "whmcs",
  "conversations": [
    {
      "external_id": "12345",
      "subject": "Вопрос про возврат",
      "description": "Пользователь: Как запросить возврат?\nСотрудник: Вы можете запросить возврат в течение 30 дней...",
      "status": "Closed",
      "priority": "Medium"
    }
  ]
}
```

Запустите ingest:

```bash
make ingest                                    # Ingestion документов
python scripts/ingest_tickets_from_source.py   # Ingestion примеров диалогов
```

### Способ 2: Загрузка по URL или краулинг сайта

- **Один URL**: используйте API `POST /v1/documents/fetch-from-url` с `{"url": "https://..."}` или через frontend **Documents** → Add → Fetch from URL
- **Весь сайт**: используйте API `POST /v1/documents/crawl-website` с `{"base_url": "https://example.com", "max_pages": 50}` или через frontend **Documents** → Crawl website

### Способ 3: Краулинг тикетов WHMCS (через frontend)

1. Перейдите в **Crawl** (сайдбар)
2. Введите **Base URL** (например, `https://billing.example.com`)
3. **Вход в WHMCS**:
   - **Вариант A (Cookies)**: войдите в WHMCS в браузере → DevTools → Application → Cookies → скопируйте JSON → вставьте в поле "Session cookies" → Save cookies
   - **Вариант B (Credentials)**: введите username, password (и TOTP при необходимости) → нажмите "Login & Crawl"
4. **Проверьте соединение** → если OK, нажмите **Crawl tickets**
5. Перейдите в **Sample conversations** (Tickets) → просмотрите каждый тикет → **одобрите** качественные тикеты
6. **Экспортируйте одобренные** → `POST /v1/admin/ingest-tickets-to-file` (или соответствующая кнопка), чтобы записать в `sample_conversations.json`
7. Запустите `python scripts/ingest_tickets_from_source.py`, чтобы выполнить эмбеддинг и индексацию

### Способ 4: Импорт из дампа SQL WHMCS

Если у вас есть дамп WHMCS (например, `source/greenvps_whmcs.sql`):

```bash
make import-whmcs-dry   # Сначала проверьте парсинг
make import-whmcs       # Выполните фактический импорт
```
Этот проект улучшает качество работы чат-бота за счёт структурированной оценки, оптимизации промптов и непрерывных циклов обратной связи.

Работает на базе [OptyxStack AI Optimization](https://optyxstack.com/ai-optimization)
 для повышения точности, релевантности и надёжности в масштабе.

Затем одобрите тикеты в **Sample conversations** и выполните ingest, как в шагах 6–7 способа 3.

### Работа с чатом (API)

1. **Создайте диалог**:
   ```bash
   curl -X POST http://localhost:8000/v1/conversations \
     -H "Authorization: Bearer YOUR_JWT" \
     -H "Content-Type: application/json" \
     -d '{"source_type": "ticket", "source_id": "TKT-123"}'
   ```
2. **Отправьте сообщение** (синхронно или в потоке):
   ```bash
   curl -X POST http://localhost:8000/v1/conversations/{CONV_ID}/messages \
     -H "Authorization: Bearer YOUR_JWT" \
     -H "Content-Type: application/json" \
     -d '{"content": "What is your refund policy?"}'
   ```
3. Ответ содержит `answer` (сгенерирован через RAG) и `debug_metadata` (ретривал, доказательства).

### Frontend — основные страницы

| Страница | Назначение |
|------|---------|
| **Conversations** | Список диалогов, создание нового, чат |
| **Sample conversations** | Просмотр собранных/импортированных тикетов, одобрение/отклонение, экспорт одобренных |
| **Documents** | CRUD документов, загрузка URL, краулинг сайта, повторный краулинг |
| **Crawl** | Настройка WHMCS, сохранение cookies, краулинг тикетов |
| **Dashboard** | Статистика токенов, ретривала, эскалаций |
| **Intents** | CRUD интентов (классификация запросов) |
| **Doc Types** | CRUD типов документов (policy, faq, pricing, …) |
| **Settings** | Системный промпт, конфигурация LLM, брендинг, доменные термины |
| **API Tokens** | Создание/отзыв API-токена (sk_*) |
| **API Reference** | Документация API |

### Интеграция с внешними системами

- **Suggested reply (платформенно-независимо)**: вызовите `POST /v1/reply/generate` с `query` = содержимое тикета/чата. Создание диалога не требуется. Используйте для WHMCS, Zendesk, livechat или любой helpdesk.
- **Livechat / тикет-система (чат-сценарий)**: вызовите `POST /v1/conversations` с `source_type: "livechat"` или `"ticket"`, `source_id` = ID из вашей системы. Когда пользователь отправляет сообщение, вызывайте `POST /v1/conversations/{id}/messages` и отображайте пользователю `answer`.
- **Webhook**: вы можете обернуть API в свой webhook-эндпоинт, чтобы принимать запросы от livechat/тикет-платформ.

### Устранение неполадок

| Проблема | Решение |
|-------|------------|
| Логин во frontend возвращает 401 | Проверьте `JWT_SECRET` в `.env`, убедитесь, что выполнили `make create-admin` |
| Краулинг WHMCS не работает | Cookies истекли → войдите в WHMCS снова, скопируйте новые cookies |
| Ingest без данных | Проверьте, что файлы в `source/` имеют корректный формат (pages, conversations), выполните `make ingest-dry` для просмотра логов |
| API возвращает 401 | Используйте Bearer JWT (из `/auth/login`) или валидный `X-API-Key` |
| Ошибка OpenSearch/Qdrant | Убедитесь, что все сервисы здоровы: `docker-compose ps` |

## Аутентификация

API поддерживает **три метода аутентификации**:

1. **Bearer JWT** – из `POST /v1/auth/login` (username/password)
2. **X-API-Key** – env `API_KEY` или API-токен из БД (sk_*)
3. **X-Admin-API-Key** – для админ-эндпоинтов (env `ADMIN_API_KEY` или JWT с ролью admin)

**Создание админа** (после миграции 011):

```bash
make create-admin
# Или: python -m scripts.create_admin_user
```

**API-токены** (sk_*): создаются через `POST /v1/auth/tokens` (требуется Bearer JWT). Токены хранятся в БД и могут быть отозваны.

## API эндпоинты

### Auth

| Метод | Эндпоинт | Описание |
|--------|----------|-------------|
| POST | `/v1/auth/login` | Логин (username, password) → JWT |
| GET | `/v1/auth/me` | Текущий пользователь (Bearer JWT) |
| GET | `/v1/auth/tokens` | Список API-токенов |
| POST | `/v1/auth/tokens` | Создание API-токена |
| DELETE | `/v1/auth/tokens/{token_id}` | Отзыв токена |

### Conversations (Диалоги)

| Метод | Эндпоинт | Описание |
|--------|----------|-------------|
| GET | `/v1/conversations` | Список (пагинация, фильтр: source_type, source_id) |
| POST | `/v1/conversations` | Создание (source_type: ticket/livechat, source_id) |
| GET | `/v1/conversations/{id}` | Детали + сообщения |
| PATCH | `/v1/conversations/{id}` | Обновление метаданных |
| DELETE | `/v1/conversations/{id}` | Удаление |
| POST | `/v1/conversations/{id}/messages` | Отправка сообщения (синхронно) |
| POST | `/v1/conversations/{id}/messages:stream` | Отправка сообщения (SSE) |

### Suggest Reply (платформенно-независимо)

| Метод | Эндпоинт | Описание |
|--------|----------|-------------|
| POST | `/v1/reply/generate` | Генерация предложенного ответа (ticket, livechat, helpdesk). Stateless, диалог не требуется. |

### Tickets (Тикеты)

| Метод | Эндпоинт | Описание |
|--------|----------|-------------|
| GET | `/v1/tickets` | Список (пагинация, фильтр: status, approval_status, q) |
| GET | `/v1/tickets/{id}` | Детали тикета |

### Documents (Документы)

| Метод | Эндпоинт | Описание |
|--------|----------|-------------|
| GET | `/v1/documents` | Список (пагинация, фильтр: doc_type, q) |
| GET | `/v1/documents/{id}` | Детали |
| POST | `/v1/documents` | Создание документа (ingest) |
| POST | `/v1/documents/fetch-from-url` | Получение содержимого по URL |
| POST | `/v1/documents/crawl-website` | Краулинг сайта |
| POST | `/v1/documents/re-crawl-all` | Повторный краулинг всех документов |
| POST | `/v1/documents/upload` | Загрузка документа |
| POST | `/v1/documents/{id}/re-crawl` | Повторный краулинг одного документа |
| PATCH | `/v1/documents/{id}` | Обновление метаданных |
| DELETE | `/v1/documents/{id}` | Удаление |

### Admin (Bearer JWT admin / X-Admin-API-Key)

| Метод | Эндпоинт | Описание |
|--------|----------|-------------|
| POST | `/v1/admin/ingest` | Ingestion документов (очередь Celery) |
| POST | `/v1/admin/ingest-from-source` | Ingestion из source/ (синхронно) |
| POST | `/v1/admin/save-whmcs-cookies` | Сохранение cookies WHMCS |
| POST | `/v1/admin/check-whmcs-cookies` | Проверка cookies |
| GET | `/v1/admin/whmcs-cookies` | Получение сохранённых cookies |
| GET | `/v1/admin/config/whmcs` | Настройки по умолчанию WHMCS |
| POST | `/v1/admin/crawl-tickets` | Краулинг тикетов WHMCS |
| PATCH | `/v1/admin/tickets/{id}/approval` | Обновление статуса одобрения (pending/approved/rejected) |
| POST | `/v1/admin/ingest-tickets-to-file` | Экспорт одобренных тикетов → sample_conversations.json |
| GET/PUT | `/v1/admin/config/llm` | Конфигурация LLM |
| GET/PUT | `/v1/admin/config/archi` | Конфигурация архитектуры (normalizer, evidence и т.д.) |
| GET/PUT | `/v1/admin/config/system-prompt` | Системный промпт |
| GET/PUT | `/v1/admin/config/{key}` | Конфигурация приложения (общая) |
| POST | `/v1/admin/config/refresh-cache` | Обновление кэша конфигурации |
| POST | `/v1/admin/config/auto-generate-from-domain` | Автогенерация брендинга из домена |
| GET/POST/PUT/DELETE | `/v1/admin/intents` | CRUD интентов |
| GET/POST/PUT/DELETE | `/v1/admin/doc-types` | CRUD типов документов |

### Health & Dashboard

| Метод | Эндпоинт | Описание |
|--------|----------|-------------|
| GET | `/v1/health` | Проверка здоровья |
| GET | `/v1/metrics` | Метрики Prometheus |
| GET | `/v1/dashboard/stats` | Стоимость токенов, hit-rate ретривала, частота эскалаций |

## Примеры cURL-запросов

### Логин

```bash
curl -X POST http://localhost:8000/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "your-password"}'
```

### Создание диалога (с Bearer JWT или X-API-Key)

```bash
curl -X POST http://localhost:8000/v1/conversations \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_JWT" \
  -d '{"source_type": "ticket", "source_id": "TKT-12345", "metadata": {}}'
```

### Отправка сообщения

```bash
curl -X POST http://localhost:8000/v1/conversations/{CONV_ID}/messages \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_JWT" \
  -H "X-External-User-Id: user-123" \
  -d '{"content": "What is your refund policy?"}'
```

### Генерация предложенного ответа (платформенно-независимо)

```bash
curl -X POST http://localhost:8000/v1/reply/generate \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_JWT" \
  -d '{
    "query": "What is your refund policy? I want to cancel my order.",
    "source_type": "ticket",
    "source_id": "TKT-12345"
  }'
```

Ответ: `{ "answer": "...", "decision": "PASS"|"ASK_USER"|"ESCALATE", "followup_questions": [], "citations": [...], "confidence": 0.9 }`

### Ingestion документов

```bash
curl -X POST http://localhost:8000/v1/admin/ingest \
  -H "Content-Type: application/json" \
  -H "X-Admin-API-Key: admin-key" \
  -d '{
    "documents": [
      {
        "url": "https://example.com/refund-policy",
        "title": "Refund Policy",
        "raw_text": "Full refund within 30 days...",
        "doc_type": "policy"
      }
    ]
  }'
```

## Конфигурация

| Переменная | По умолчанию | Описание |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql+asyncpg://...` | PostgreSQL (async) |
| `DATABASE_URL_SYNC` | `postgresql://...` | PostgreSQL (sync, Celery) |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis |
| `OPENSEARCH_HOST` | `http://localhost:9200` | OpenSearch |
| `QDRANT_HOST` | `localhost` | Qdrant |
| `OPENAI_API_KEY` | - | Обязателен для эмбеддингов/LLM |
| `API_KEY` | - | Аутентификация API (пусто = dev-режим) |
| `ADMIN_API_KEY` | - | Админ-аутентификация |
| `JWT_SECRET` | `change-me-in-production` | Секрет подписи JWT (обязателен в production) |
| `JWT_EXPIRE_MINUTES` | `10080` (7 дней) | Срок действия JWT |
| `OBJECT_STORAGE_URL` | - | MinIO/S3 (например, http://minio:9000) |
| `LLM_MODEL` | `gpt-5.2` | Модель LLM |
| `LLM_MAX_TOKENS` | `2048` | Максимум токенов |
| `APP_NAME` | - | Название компании/приложения для брендинга (приветствие, заголовок) |
| `NORMALIZER_DOMAIN_TERMS` | - | Сущности через запятую (например, vps,windows,linux,pricing) |
| `NORMALIZER_SLOTS_ENABLED` | `false` | Включить извлечение слотов (product_type, os, billing_cycle, region) |
| `NORMALIZER_SLOT_PRODUCT_TYPES` | - | Типы продуктов для слотов (например, vps,dedicated,vds). Пусто = выключено |
| `NORMALIZER_SLOT_OS_TYPES` | - | Типы ОС для слота os (например, windows,linux,macos). Пусто = выключено |
| `CORS_ORIGINS` | `*` | Разрешённые CORS-источники. Через запятую (например, `https://app.example.com`). `*` = разрешить все (dev) |
| `DOCS_ENABLED` | `true` | Включить `/docs` и `/redoc`. В production установите `false`, чтобы скрыть документацию API |

## Скрипты

| Скрипт | Описание |
|--------|-------------|
| `scripts/init_db.py` | Создание БД и выполнение миграций |
| `scripts/create_admin_user.py` | Создание первого админа (запускать после миграции 011) |
| `scripts/ingest_from_source.py` | Ingestion документов из source/ |
| `scripts/ingest_tickets_from_source.py` | Ingestion тикетов из sample_conversations.json |
| `scripts/import_whmcs_sql_dump_to_tickets.py` | Импорт тикетов из source/*.sql |
| `scripts/crawl_whmcs_tickets.py` | Краулинг тикетов WHMCS (CLI) |
| `scripts/whmcs_login_browser.py` | Открыть браузер для входа в WHMCS, получить cookies |

### Команды Makefile

```bash
make init-db       # Выполнение миграций
make create-admin  # Создание админа
make ingest        # Ingestion документов из source/
make ingest-dry    # Сухой прогон: загрузка документов без ingestion
make import-whmcs  # Импорт тикетов WHMCS из source/*.sql
make import-whmcs-dry  # Сухой прогон: проверка парсинга SQL
```

## Frontend

```bash
cd frontend && npm install && npm run dev
# http://localhost:5173
```

Или через Docker: `docker-compose up -d frontend` → http://localhost:5174

**Основные страницы**: Логин, Диалоги, Примеры диалогов (тикеты), Документы, Краулинг (WHMCS), Дашборд, Интенты, Типы документов, Настройки, API-токены, Справочник API.

## Структура проекта

```
app/
  main.py              # FastAPI-приложение
  api/routes/          # auth, conversations, reply, tickets, documents, admin, health, dashboard
  services/            # retrieval, LLM, ingestion, ticket_db, ticket_loaders, source_loaders
  search/              # OpenSearch, Qdrant, reranker, embeddings
  crawlers/            # краулер WHMCS (Playwright)
  db/                  # модели, сессия
  core/                # config, auth, logging, rate limit, tracing, gateway
worker/
  celery_app.py
  tasks.py             # задачи ingestion
frontend/              # React + Vite (CRUD, чат, UI краулинга)
alembic/               # миграции
scripts/               # init_db, create_admin_user, ingest_from_source, ingest_tickets_from_source, import_whmcs_sql_dump_to_tickets, crawl_whmcs_tickets, whmcs_login_browser
docs/                  # Документация проекта (архитектура, процессы, качество) — см. "Документация" ниже
source/                # sample_docs.json, sample_conversations.json, custom_docs.json, *.sql
```

## Документация

Подробная документация по проекту находится в папке `docs/` — прочитайте соответствующий документ, прежде чем погружаться в код:

| Документ | Описание |
|---|---|
| `docs/01_project_structure.md` | Карта проекта: дерево каталогов, назначение модулей, внешние зависимости |
| `docs/02_architecture.md` | Архитектура и паттерны, поток данных RAG, поток ingestion, кэширование и конфигурация |
| `docs/03_execution_flow.md` | Жизненный цикл приложения, бизнес-процессы, middleware, маршруты, обработка ошибок |
| `docs/04_code_quality.md` | Оценка качества кода, технический долг, замечания по безопасности и надёжности |
| `docs/05_optimization_roadmap.md` | Предложения по рефакторингу и оптимизации (приоритизированные) |

## Тесты

```bash
pip install -e ".[dev]"
pytest tests/ -v
```
