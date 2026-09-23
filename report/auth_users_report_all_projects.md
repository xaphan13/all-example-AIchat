# Сводный отчёт по авторизации и пользователям во всех 6 проектах

> Дата: 30.08.2026
> Источники: `agents_docs/<проект>/*.md` + проверка реального кода в рабочих деревьях
> (`AI-Chatbot/app/api/v1/users.py`, `rag-knowledge-base-chatbot/app/api/routes/auth.py`,
> grep по `Quorum/backend` и др.).
> Формат: сравнительный обзор — где auth есть, где нет, как устроены пользователи и роли.

---

## 1. Резюме: одна картинка на все 6 проектов

Полноценная пользовательская авторизация есть **только в 2 из 6 проектов** — AI-Chatbot
и rag-knowledge-base-chatbot. Остальные четыре — прототипы без пользователей, где
единственные секреты — это API-ключи провайдеров LLM.

| Критерий | AI-Chatbot | GroqStreamChain | LLM Council | OpenAI Responses | Quorum | RAG Chatbot |
|---|---|---|---|---|---|---|
| **Auth есть?** | ✅ да | ❌ нет | ❌ нет | ❌ нет | ❌ нет | ✅ да (самая полная) |
| **Механизм** | FastAPI-Users: JWT + Cookie | — | — | — | — | Bearer JWT + `X-API-Key` + `X-Admin-API-Key` |
| **Пользователи в БД** | ✅ таблица `User` (SQLite) | — | — | — | — | ✅ `User` + `ApiToken` (PostgreSQL) |
| **Регистрация** | ✅ публичный `POST /auth/register` | — | — | — | — | ⚠️ нет self-registration, только `make create-admin` |
| **Роли** | `is_superuser`, `is_verified` (флаги, фактически не используются) | — | — | — | — | `role: user / admin` (enum, RBAC) |
| **Токены/сессии** | JWT в cookie `fastapiusersauth`, lifetime 3600с | — | — | — | — | JWT 7 дней + отзывные API-токены `sk_*` (hash в БД) |
| **Frontend auth** | cookie-сессия, редиректы | — | — | — | — | `AuthContext.tsx`, Bearer из `localStorage`, флаг `AUTH_REQUIRED` |
| **Дефолтный секрет** | ⚠️ `SECRET = "your-secret-key-change-this-in-production"` | — | — | — | — | ⚠️ `JWT_SECRET = "change-me-in-production"` (enforced в compose, не локально) |
| **Rate limiting на login** | ❌ нет (brute-force) | — | — | — | — | ⚠️ есть, но fail-open при недоступном Redis |

---

## 2. AI-Chatbot — единственный «классический» auth из коробки

**Реализация:** `app/api/v1/users.py` — FastAPI-Users с двумя backend'ами на общей
`JWTStrategy` (secret=`SECRET`, lifetime 3600с):

- `cookie_auth_backend` (`CookieTransport`, cookie `fastapiusersauth`, HttpOnly,
  max_age=3600) — для браузера; к нему привязаны роутеры login/register;
- `jwt_auth_backend` (`BearerTransport`, tokenUrl `auth/jwt/login`) — для API-клиентов.

**Эндпоинты:**

| Метод | Путь | Auth | Назначение |
|---|---|---|---|
| POST | `/auth/register` | нет | Регистрация (JSON: email, password, full_name) |
| POST | `/auth/login` | нет | Вход (form-urlencoded: `username=<email>&password=...`) |
| POST | `/auth/logout` | `current_user` | Выход (сброс cookie) |
| POST | `/auth/jwt/login` | нет | Вход через Bearer-токен (API) |
| GET/PATCH | `/users/me` | `current_user` | Профиль |

**Поток:** `Depends(current_user)` → JWT из cookie `fastapiusersauth` → декодирование →
запрос `User` из SQLite через `SQLAlchemyUserDatabase`. При неудаче — 401.

**Модель пользователя:** SQLAlchemy 2.0 (`app/models/users.py`), id (UUID), email,
full_name, hashed_password, `is_active`, `is_superuser`, `is_verified`. Пароли — bcrypt
(встроен в FastAPI-Users). UserManager — `app/services/user_manager.py`.

**Риски:**
- дефолтный `SECRET` в `app/core/config.py` — если не задан `.env`, JWT подписываются
  предсказуемым ключом (полная компрометация);
- нет rate limiting на `/auth/login` (brute-force) и на `/api/chat`;
- двойная auth-конфигурация (JWT + Cookie) избыточна для SSR-фронтенда — нужен только Cookie;
- `/health` требует auth — недоступен для мониторинга;
- в roadmap (`05_optimization_roadmap.md`, P3) предложено вынести auth-конфиг в `app/core/security.py`.

## 3. GroqStreamChain — auth отсутствует полностью

Любой клиент может подключиться к `WS /ws/chat`: нет токенов, сессий, API-key проверки
(`04_code_quality.md`: «Аутентификация — ✘ Отсутствует»). «Сессии» в проекте — это только
чат-сессии в памяти (`chat_sessions[session_id]`), не имеющие отношения к пользователям.

В roadmap (`05_optimization_roadmap.md`) предложен вариант: query-token
`ws://host/ws/chat?token=...` + проверка через FastAPI dependency + новый `services/auth.py`.
Это план, не реализация.

## 4. llm-council-karpathy — auth отсутствует

Нет ни auth, ни authorization, ни межпользовательского состояния. Единственный
`Authorization: Bearer` в коде — к OpenRouter (`OPENROUTER_API_KEY`): это авторизация
исходящих LLM-вызовов, не пользователей. Диалоги хранятся в JSON-файлах
`data/conversations/` без привязки к владельцу (плюс риск path traversal через
`conversation_id`). Оценка безопасности в `04_code_quality.md`: 4/10, «нет auth» — первый
пункт.

## 5. openai-responses-python-quickstart — auth отсутствует

Проект без пользователей: состояние диалога хранится на стороне OpenAI (Conversations API).
Единственный «ключ» — `OPENAI_API_KEY`, вводимый через UI `/setup` и записываемый в `.env`
(`POST /setup/api-key`, `routers/setup.py`) — это конфигурация, а не авторизация.

Свои auth-смежные риски (`04_code_quality.md`):
- IDOR: `GET /files/{file_id}/content` отдаёт произвольный файл по известному id без auth;
- path traversal в `store_file`;
- поле «auth» в настройках MCP-серверов — это auth к внешнему MCP-серверу, не к приложению.

## 6. Quorum — auth отсутствует (заявлена в roadmap)

Проверено по исходникам: в бэкенде **нет модели User, нет auth-dependency, нет логина** —
слово «user» встречается только как роль сообщения в истории чата (`role: "user"` в
`core/models.py`, `infrastructure/database/models.py`). PostgreSQL хранит
conversations/messages/agents, но без владельцев.

При этом:
- `GET /api/settings?mask_keys=false` позволяет получить **полные API-ключи** — комментарий
  «for authenticated requests only» в `routes/settings.py:67` не подкреплён никакой
  аутентификацией (🟠 MEDIUM, `04_code_quality.md:237`);
- cleanup endpoint трекинга токенов (`TokenTrackingManager`) — без auth;
- в `05_optimization_roadmap.md` Phase 3 «Security & Auth»: JWT-аутентификация
  (fastapi-users или custom) + rate limiting, оценка «Auth + rate limiting — 5-10 дней, 🔴 P0».
  Это план, не реализация.

## 7. rag-knowledge-base-chatbot — самая развитая модель (3 способа)

**Реализация:** собственный код (без FastAPI-Users):
`app/api/routes/auth.py` (роуты) + `app/core/auth.py` (dependencies) +
`app/services/auth_service.py` (JWT encode/decode, bcrypt, валидация токенов).

**Три способа авторизации:**

1. **Bearer JWT** — `POST /v1/auth/login` (username/password) → bcrypt verify →
   JWT HS256, `JWT_EXPIRE_MINUTES=10080` (7 дней). `GET /v1/auth/me` — текущий
   пользователь. Rate limit bypass — только для admin Bearer JWT.
2. **`X-API-Key`** — env `API_KEY` (или dev-mode, если пустой) **или** токен из БД
   формата `sk_*` (lookup по hash).
3. **`X-Admin-API-Key`** — для админ-эндпоинтов (env `ADMIN_API_KEY` или JWT с
   `role=admin`); проверка `require_admin` → 403.

**API-токены (`sk_*`):** создаются через `POST /v1/auth/tokens` (требуется Bearer JWT),
plain-токен показывается **один раз**, в БД хранится `token_hash` + `token_prefix`,
есть `scopes`, `expires_at`, `last_used_at`. Отзыв — `DELETE /v1/auth/tokens/{token_id}`
(с проверкой владельца). Список — `GET /v1/auth/tokens`.

**Модель пользователя:** `User` (id, username, email, `password_hash`, `is_active`,
`role` — enum `UserRole`: user/admin) + `ApiToken`. Регистрации через API нет —
админ создаётся командой `make create-admin`. Токены хранятся как hash, пароли — bcrypt.

**Auth flow (из `03_execution_flow.md`):**
1. Login: `POST /auth/login` → bcrypt verify → JWT → `Authorization: Bearer`.
2. API key: `X-API-Key` → env `API_KEY` или DB token `sk_*` (hash lookup).
3. Admin: `X-Admin-API-Key` / JWT с `role=admin` / `sk_*` от admin user.
4. Rate limit bypass — только для admin Bearer JWT.

**Frontend:** `AuthContext.tsx` — login/logout, при старте проверка токена через
`GET /auth/me`; Bearer из `localStorage` (`support_ai_token`) подставляется в
request-интерцепторе axios; запасной `X-API-Key` через `VITE_API_KEY` /
`VITE_ADMIN_API_KEY` (для Docker-сборок); флаг `AUTH_REQUIRED` позволяет **полностью
отключить авторизацию** для локальных сборок.

**Риски (`04_code_quality.md`):**
- дефолт `JWT_SECRET="change-me-in-production"` — enforced в docker-compose
  (`JWT_SECRET:?must be set`), но локально dev-mode без секрета;
- JWT в `localStorage` вместо HttpOnly-cookie — XSS-риск;
- rate limiting fail-open при недоступном Redis;
- `/metrics` без auth — утечка метрик;
- OpenSearch security отключён в compose (нет basic auth/TLS).

---

## 8. Ключевые выводы

1. **Полноценный пользовательский auth есть только в 2 из 6 проектов**: AI-Chatbot
   (готовое решение FastAPI-Users, browser-oriented, cookie) и RAG Chatbot (собственный,
   enterprise-oriented: JWT + отзывные API-токены `sk_*` + роли user/admin + admin-key).
2. **Паттерн «дефолтный секрет» повторяется** в обоих проектах с auth (`SECRET` в
   AI-Chatbot, `JWT_SECRET` в RAG) — типовой P0 для обоих.
3. **Остальные 4 проекта** (GroqStreamChain, LLM Council, OpenAI Responses, Quorum) —
   прототипы без каких-либо пользователей; единственные ключи в них — ключи провайдеров
   LLM, и в Quorum эти ключи можно вычитать через незащищённый settings-эндпоинт.
4. **Роли**: только RAG имеет настоящую RBAC (user/admin); в AI-Chatbot есть лишь флаги
   `is_superuser`/`is_verified`, которые фактически нигде не используются для
   разграничения доступа.
5. **Хранение токенов на клиенте**: AI-Chatbot — HttpOnly-cookie (безопаснее),
   RAG — `localStorage` (уязвимее к XSS, но удобнее для API-интеграций).
6. Если нужна основа для добавления auth в остальные проекты: для FastAPI-проектов
   проще всего взять подход AI-Chatbot (FastAPI-Users), для API-интеграций — модель
   токенов `sk_*` из RAG Chatbot.
