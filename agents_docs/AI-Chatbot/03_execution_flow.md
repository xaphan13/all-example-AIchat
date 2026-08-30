# 03 — Логика и работа кода

## Жизненный цикл приложения

### Инициализация

Жизненный цикл управляется **uvicorn** — ASGI-сервером. Приложение не определяет кастомные `lifespan` или `startup`/`shutdown` event handlers.

**Порядок инициализации (при импорте `app.main:app`):**

1. **Импорт `app.core.config`** → создание singleton `settings` (чтение `.env` и переменных окружения)
2. **Импорт `app.db.session`** → создание `engine` (async SQLAlchemy engine для SQLite) и `AsyncSession` (sessionmaker)
3. **Импорт `app.services.chat`** → создание singleton `client = AsyncOpenAI(...)` с `api_key=GITHUB_TOKEN`, `base_url=https://models.github.ai/inference/`
4. **Импорт `app.api.v1.users`** → регистрация `FastAPIUsers` с двумя auth-backend'ами (JWT + Cookie), создание роутеров `login_router`, `users_router`, `register_router`, dependency `current_user`
5. **Импорт `app.api.v1.chat`** → создание `router` с эндпоинтом `POST /chat`
6. **Выполнение `app/main.py`** → создание `app = FastAPI()`, монтирование static files, подключение роутеров, регистрация HTML-роутов

> **Критично:** `app/main.py:20` вызывает `StaticFiles(directory="app/static")`, но директория `app/static/` **не существует**. Это вызовет исключение при запуске приложения.

### Запуск

```bash
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Флаг `--reload` включает hot-reload при изменении файлов (dev-режим). В production-режиме флаг снимается.

### Завершение работы

**Не реализовано.** Нет `shutdown` event handler'а, который бы:
- Закрывал async engine (`engine.dispose()`)
- Закрывал соединения OpenAI-клиента
- Освобождал ресурсы

uvicorn корректно закрывает event loop, но явная очистка ресурсов отсутствует.

---

## Ключевые бизнес-процессы

### Процесс 1: Чат с AI

**Endpoint:** `POST /api/chat` (`app/api/v1/chat.py:12`)

| Шаг | Компонент | Действие |
|-----|-----------|----------|
| 1 | Браузер (`index.html:187`) | JS-клиент отправляет `fetch('/api/chat', { method: 'POST', body: JSON.stringify({prompt: message}) })` |
| 2 | FastAPI | Роутинг: prefix `/api` → `bot_router` → путь `/chat` |
| 3 | FastAPI | Валидация тела запроса через `ChatRequest` (Pydantic): поле `prompt: str` обязательно |
| 4 | FastAPI | Resolution `Depends(current_user)`: извлечение JWT из cookie `fastapiusersauth` → декодирование → запрос `User` из БД через `SQLAlchemyUserDatabase`. При неудаче → `401 Unauthorized` |
| 5 | `app/services/chat.py:11` | Вызов `get_chat_response(prompt)` |
| 6 | `app/services/chat.py:15-18` | Формирование сообщения: конкатенация системного промпта `"Hey ChatGPT, you are a AI chatbot..."` + пользовательский ввод |
| 7 | `app/services/chat.py:19-22` | `await client.chat.completions.create(model="openai/gpt-4o", messages=[...])` — HTTP-запрос к GitHub Models API |
| 8 | `app/services/chat.py:23` | Извлечение `response.choices[0].message.content.strip()` или `""` если `choices` пуст |
| 9 | `app/api/v1/chat.py:17` | Возврат `{"response": "<текст>"}` → JSON → браузер |
| 10 | Браузер (`index.html:203-204`) | Удаление typing-индикатора, отрисовка ответа через `addMessage(data.response, 'ai')` |

**Особенности:**
- Каждый запрос — **stateless**: история сообщений не передаётся и не сохраняется
- Системный промпт жёстко вшит в код (не настраивается)
- Нет таймаута на запрос к LLM API
- Нет обработки ошибок API (timeout, 5xx, rate limit)

### Процесс 2: Регистрация пользователя

**Endpoint:** `POST /auth/register` (роутер FastAPI-Users, `app/api/v1/users.py:48`)

| Шаг | Компонент | Действие |
|-----|-----------|----------|
| 1 | Браузер (`signup.html:120`) | `fetch('/auth/register', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({email, password, full_name}) })` |
| 2 | FastAPI-Users | Валидация через `UserCreate` (Pydantic): `email`, `password`, `full_name` |
| 3 | `UserManager` (`app/services/user_manager.py:13`) | Хеширование пароля (bcrypt через FastAPI-Users) |
| 4 | `SQLAlchemyUserDatabase` | `INSERT INTO user (id, email, hashed_password, is_active, is_superuser, is_verified, full_name)` |
| 5 | `UserManager.on_after_register()` | `print(f"User {user.id} has registered.")` — логирование в stdout |
| 6 | FastAPI-Users | Возврат `UserRead` JSON (id, email, full_name, is_active, is_superuser, is_verified) |
| 7 | Браузер (`signup.html:134-138`) | Показ success-сообщения → redirect на `/login` через 2 секунды |

### Процесс 3: Вход в систему (Cookie-auth)

**Endpoint:** `POST /auth/login` (роутер FastAPI-Users, `app/api/v1/users.py:46`)

| Шаг | Компонент | Действие |
|-----|-----------|----------|
| 1 | Браузер (`login.html:114`) | `fetch('/auth/login', { method: 'POST', headers: {'Content-Type': 'application/x-www-form-urlencoded'}, body: 'username=<email>&password=<password>' })` |
| 2 | FastAPI-Users (cookie_auth_backend) | Поиск пользователя по email → проверка пароля (bcrypt) |
| 3 | `JWTStrategy` (`app/api/v1/users.py:20`) | Генерация JWT: `secret=SECRET`, `lifetime=3600с` |
| 4 | `CookieTransport` (`app/api/v1/users.py:33`) | Установка cookie `fastapiusersauth=<jwt>`, `max_age=3600`, `HttpOnly` |
| 5 | FastAPI-Users | HTTP 200 + `Set-Cookie` |
| 6 | Браузер (`login.html:122`) | `window.location.href = '/chat'` |

### Процесс 4: Выход из системы

**Endpoint:** `POST /auth/logout` (роутер FastAPI-Users)

| Шаг | Компонент | Действие |
|-----|-----------|----------|
| 1 | Браузер (`index.html:278`) | `fetch('/auth/logout', { method: 'POST' })` |
| 2 | FastAPI-Users (cookie_auth_backend) | Удаление cookie `fastapiusersauth` (Set-Cookie с max_age=0) |
| 3 | Браузер | `window.location.href = '/'` (redirect на лендинг) |

---

## Роутинг и Middleware

### Таблица роутов

| Метод | Путь | Источник | Аутентификация | Назначение |
|-------|------|----------|----------------|------------|
| `GET` | `/` | `app/main.py:31` | Нет | Лендинг-страница (`landing.html`) |
| `GET` | `/login` | `app/main.py:37` | Нет | Страница входа (`login.html`) |
| `GET` | `/signup` | `app/main.py:43` | Нет | Страница регистрации (`signup.html`) |
| `GET` | `/chat` | `app/main.py:49` | `current_user` (обязательная) | Чат-интерфейс (`index.html`) |
| `GET` | `/health` | `app/main.py:55` | `current_user` (обязательная) | Health check |
| `POST` | `/api/chat` | `app/api/v1/chat.py:12` | `current_user` (обязательная) | Отправка сообщения AI |
| `POST` | `/auth/login` | FastAPI-Users (cookie) | Нет | Вход (form-urlencoded) |
| `POST` | `/auth/logout` | FastAPI-Users (cookie) | `current_user` | Выход |
| `POST` | `/auth/register` | FastAPI-Users | Нет | Регистрация (JSON) |
| `GET` | `/users/me` | FastAPI-Users | `current_user` | Информация о текущем пользователе |
| `PATCH` | `/users/me` | FastAPI-Users | `current_user` | Обновление профиля |
| `GET` | `/auth/jwt/login` | FastAPI-Users (JWT) | Нет | Вход через Bearer-токен |
| `GET` | `/docs` | FastAPI (auto) | Нет | Swagger UI |
| `GET` | `/static/*` | `StaticFiles` | Нет | Статические файлы (**директория не существует**) |

### Middleware

**Кастомные middleware отсутствуют.** Нет:
- CORS middleware (фронтенд и бэкенд на одном origin, но API недоступен для внешних клиентов)
- Rate limiting middleware
- Request logging middleware
- GZip middleware
- TrustedHost middleware

Единственная "middleware"-обработка — встроенная в FastAPI валидация Pydantic и dependency resolution.

---

## Обработка ошибок

### Состояние: **Не реализовано на уровне приложения**

В `app/main.py` **нет**:
- Глобального `@app.exception_handler(...)` для кастомных исключений
- Middleware для перехвата `Exception`
- Структурированного формата ошибок (все ошибки отдаются в дефолтном FastAPI-формате `{"detail": "..."}`)

### Обработка на уровне отдельных компонентов

| Компонент | Обработка ошибок | Оценка |
|-----------|------------------|--------|
| `app/api/v1/chat.py:13` | Нет `try/except` вокруг `get_chat_response()`. Ошибка LLM API → необработанное исключение → HTTP 500 | ❌ Недостаточно |
| `app/services/chat.py:19` | Нет `try/except` вокруг `client.chat.completions.create()`. Timeout, 5xx, rate limit → необработанное исключение | ❌ Недостаточно |
| Браузер `index.html:205-208` | `catch (error)` → показывает "Sorry, I encountered an error" | ✅ Базовая обработка на клиенте |
| Браузер `login.html:128` | `catch` → showError('Network error') | ✅ Базовая |
| Браузер `signup.html:143` | `catch` → showMessage('Network error') | ✅ Базовая |
| FastAPI-Users (встроенная) | 401 при неверных учётных данных, 400 при дубликате email | ✅ Встроенная |

### Логирование

**Состояние: практически отсутствует.**

| Компонент | Механизм | Оценка |
|-----------|----------|--------|
| `app/services/user_manager.py:18` | `print(f"User {user.id} has registered.")` | ❌ `print()` вместо `logging` |
| `app/db/session.py:5` | `echo=settings.DEBUG` — вывод SQL в stdout при `DEBUG=True` | ⚠️ Утечка SQL в логах |
| Остальные компоненты | Логирование отсутствует | ❌ Нет |

Нет настройки `logging.config`, нет структурного логирования (JSON), нет уровней логирования (DEBUG/INFO/WARNING/ERROR), нет корреляционных ID для трассировки запросов.
