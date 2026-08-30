# AI Chatbot Assistant

[![Python](https://img.shields.io/badge/Python-3.13+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.116+-green.svg)](https://fastapi.tiangolo.com/)
[![GitHub Models](https://img.shields.io/badge/GitHub%20Models-AI%20Inference-purple.svg)](https://github.blog/ai-and-ml/llms/solving-the-inference-problem-for-open-source-ai-projects-with-github-models/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Современное полнофункциональное веб-приложение — AI-чат-бот на **FastAPI** и **Jinja2**, использующее **GitHub Models** для бесплатного open-source AI-инференса. Красивый адаптивный UI с функциями реального времени и безопасной аутентификацией пользователей.

## 📚 Документация

Директория `docs/` — **единый источник истины** о проекте:

| Файл | Назначение |
|------|------------|
| [`docs/01_project_structure.md`](docs/01_project_structure.md) | Карта проекта: дерево директорий, ответственность файлов, внешние зависимости |
| [`docs/02_architecture.md`](docs/02_architecture.md) | Архитектура, паттерны проектирования, поток данных, управление состоянием/конфигурацией |
| [`docs/03_execution_flow.md`](docs/03_execution_flow.md) | Жизненный цикл приложения, бизнес-процессы, роутинг, обработка ошибок |
| [`docs/04_code_quality.md`](docs/04_code_quality.md) | Оценка качества, известные запахи кода, проблемы безопасности, узкие места |
| [`docs/05_optimization_roadmap.md`](docs/05_optimization_roadmap.md) | Дорожная карта: улучшения P0–P3, план рефакторинга, рекомендации по DX |

**Для AI-агентов по написанию кода**: см. [`AGENTS.md`](AGENTS.md) (универсальный, для всех харнесов) или [`CLAUDE.md`](CLAUDE.md) (Claude Code) — оба предписывают агентам сначала читать `docs/`, без обхода всего проекта.

## ✨ Возможности

- **🤖 AI-диалоги** — бесплатный AI-инференс через GitHub Models
- **🔐 Безопасная аутентификация** — JWT-аутентификация через FastAPI-Users
- **🎨 Современный UI** — стильный glassmorphism-дизайн на Tailwind CSS
- **📱 Адаптивная вёрстка** — отлично работает на десктопе и мобильных
- **⚡ Чат в реальном времени** — мгновенные обновления сообщений с индикатором набора текста
- **🔒 Защищённые маршруты** — доступ к чату только для аутентифицированных пользователей
- **🚀 Интеграция с GitHub** — настройка без конфигурации через GitHub Personal Access Token

## 🏗️ Технологический стек

### Бэкенд
- **FastAPI** — современный быстрый веб-фреймворк для Python (async)
- **FastAPI-Users** — полное решение по управлению пользователями (JWT + Cookie аутентификация)
- **SQLAlchemy 2.0** — асинхронный SQL-тулкит и ORM
- **SQLite** — лёгкая БД через `aiosqlite` (легко обновляется до PostgreSQL)
- **Alembic** — миграции базы данных
- **GitHub Models API** — бесплатный эндпоинт AI-инференса

### Фронтенд
- **Jinja2-шаблоны** — серверный рендеринг
- **HTML5/Tailwind CSS** — современный адаптивный стиль (CDN)
- **Lucide Icons** — красивые, единообразные иконки
- **Ванильный JavaScript** — лёгкие, быстрые взаимодействия
- **Glassmorphism-дизайн** — современные UI-тренды

## 🚀 Быстрый старт

### Предварительные требования
- Python 3.13+
- Менеджер пакетов [uv](https://docs.astral.sh/uv/) (рекомендуется)
- GitHub Personal Access Token с разрешением `models:read` (для AI-инференса)

### Установка

1. **Клонируйте репозиторий**
   ```bash
   git clone https://github.com/Sohail342/AI-Chatbot.git
   cd ai-chatbot
   ```

2. **Установите зависимости**
   ```bash
   uv sync
   ```

3. **Настройте переменные окружения**
   ```bash
   # Создайте файл .env
   touch .env

   # Впишите свой GitHub-токен и секрет
   GITHUB_TOKEN=your_github_personal_access_token
   SECRET=generate-a-random-secret-key-here
   ```

4. **Запустите миграции базы данных**
   ```bash
   uv run alembic upgrade head
   ```

5. **Запустите приложение**
   ```bash
   uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

6. **Откройте приложение**
   - 🌐 **Главное приложение**: http://localhost:8000
   - 📚 **Документация API**: http://localhost:8000/docs

> **Примечание**: приложение монтирует `StaticFiles` на `app/static/` — если этой директории нет, создайте её заранее, иначе запуск завершится ошибкой.

## 🔧 Интеграция с GitHub Models

Это приложение использует **GitHub Models** для AI-инференса — бесплатный доступ к мощным AI-моделям без платных API-ключей.

### Как это работает
- **Нулевая конфигурация**: не нужны ключи OpenAI или платные сервисы
- **GitHub-токен**: используется ваш существующий GitHub Personal Access Token
- **Совместимость с OpenAI**: работает со стандартными паттернами OpenAI SDK (`AsyncOpenAI` с собственным `base_url`)
- **Бесплатный тариф**: доступен всем пользователям GitHub и open-source проектам

### Инструкция по настройке
1. Создайте [GitHub Personal Access Token](https://github.com/settings/tokens)
2. Выдайте разрешение `models:read`
3. Добавьте токен в файл `.env`: `GITHUB_TOKEN=your_token_here`

### Пример использования API
```python
# Пример вызова GitHub Models
import requests

headers = {"Authorization": f"Bearer {GITHUB_TOKEN}", "Content-Type": "application/json"}

payload = {"model": "gpt-4o", "messages": [{"role": "user", "content": "Hello, AI!"}]}

response = requests.post(
    "https://models.github.ai/inference/chat/completions", headers=headers, json=payload
)
```

## 🎯 Руководство по использованию

### Регистрация и вход
1. Откройте http://localhost:8000
2. Нажмите "Get Started", чтобы зарегистрировать новый аккаунт
3. Войдите с вашими учётными данными
4. Откройте интерфейс AI-чата

### Возможности чата
- **Отправка сообщений**: вводите текст в поле чата и нажимайте Enter
- **Индикаторы набора текста**: видите, когда AI думает
- **Адаптивная вёрстка**: работает на всех устройствах

### API-эндпоинты
- `POST /auth/register` — регистрация пользователя
- `POST /auth/login` — аутентификация пользователя
- `POST /auth/logout` — выход пользователя
- `POST /api/chat` — отправка сообщения AI
- `GET /users/me` — получение информации о текущем пользователе
- `GET /chat` — интерфейс чата (HTML, требует аутентификации)
- `GET /health` — проверка работоспособности (требует аутентификации)

## 🎨 Дизайн

### Современные UI-элементы
- **Glassmorphism-карточки**: полупрозрачные фоны с размытием
- **Градиентные анимации**: динамические переходы цветов
- **Плавающие анимации**: лёгкое движение для вовлечённости
- **Эффекты наведения**: интерактивная обратная связь на всех элементах
- **Адаптивная сетка**: подстраивается под любой размер экрана

### Цветовая схема
- **Основной**: фиолетовые градиенты (#667eea → #764ba2)
- **Вторичный**: розовые акценты (#ec4899)
- **Фон**: тёмная тема с glass-эффектами
- **Текст**: высокая контрастность для читаемости

## 🛠️ Разработка

### Структура проекта
```
├── app/
│   ├── main.py              # Точка входа: FastAPI-приложение, HTML-роуты, подключение роутеров
│   ├── api/v1/              # Роутеры API: chat.py, users.py (конфигурация FastAPIUsers)
│   ├── core/                # config.py (Pydantic Settings), templates.py
│   ├── db/                  # base.py, session.py (async engine + get_db)
│   ├── models/              # users.py — ORM-модель User
│   ├── schemas/             # Pydantic DTO: chat.py, users.py
│   ├── services/            # chat.py (LLM-клиент), user_manager.py
│   └── templates/           # landing.html, login.html, signup.html, index.html
├── alembic/                 # Миграции базы данных
├── docs/                    # ← Единый источник истины (см. Документацию)
├── pyproject.toml           # Зависимости, конфигурация ruff/black
└── alembic.ini              # Конфигурация Alembic
```

### Добавление новых функций
1. **Бэкенд**: добавляйте новые маршруты в `app/api/v1/`
2. **Фронтенд**: обновляйте шаблоны в `app/templates/`
3. **База данных**: создавайте миграции через `uv run alembic revision --autogenerate -m "<message>"`
4. **Документация**: обновляйте соответствующий файл в `docs/`, если меняется архитектура или поток данных

### Переменные окружения
```bash
# Обязательные
GITHUB_TOKEN=your_github_personal_access_token
SECRET=your_secret_key_for_jwt

# База данных (опционально, по умолчанию: sqlite+aiosqlite:///./sqlite.db)
DATABASE_URL=sqlite+aiosqlite:///./chatbot.db

# Опционально
DEBUG=False
```

### Линт и форматирование
```bash
uv run ruff check .
uv run ruff format .
uv run black .
```

## 🧪 Тестирование

> **Статус**: автоматизированного тестового набора пока нет. Настройка тестов — часть дорожной карты — см. `docs/05_optimization_roadmap.md`.

### Ручное тестирование
- **Фронтенд**: тестируйте на разных размерах экрана
- **API**: используйте Swagger-документацию на `/docs`
- **Аутентификация**: проверяйте сценарии входа/выхода
- **AI**: проверяйте ответы GitHub Models

## 📝 Лицензия

MIT
