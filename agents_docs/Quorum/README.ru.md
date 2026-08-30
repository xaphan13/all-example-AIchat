# NoOversight — Мульти-агентная AI-платформа

**Языки:** [English](README.md) · [Русский](README.ru.md)

> **Для AI-ассистентов:** прочитайте [`AGENTS.md`](AGENTS.md) и папку [`docs/`](docs/) перед
> изучением исходного кода — это единый источник истины, избавляющий от слепого обхода всего
> репозитория.

Production-ready платформа, позволяющая нескольким AI-агентам (Claude, GPT, Gemini) коллаборировать над сложными задачами через единый API OpenRouter. Система использует интеллектуальный оркестратор для делегирования подзадач специализированным агентам и синтезирует их ответы в целостные решения.

## Обзор

NoOversight реализует лёгкую, streaming-first архитектуру для координации мульти-агентного AI. В отличие от тяжёлых фреймворков (LangGraph, CrewAI, AutoGen), система ставит на первое место поддерживаемость, производительность и real-time обратную связь с пользователем через Server-Sent Events и асинхронную обработку.

### Архитектура

**Backend**
- FastAPI с async-поддержкой
- OpenRouter для унифицированного доступа к моделям (Claude, GPT, Gemini и др.)
- PostgreSQL для персистентности диалогов
- WebSocket и SSE для real-time стриминга
- Система инструментов с возможностью web search

**Frontend**
- React 18 с TypeScript
- Tailwind CSS для стилей
- Zustand для управления состоянием
- Framer Motion для анимаций
- Стриминг сообщений в реальном времени

## Требования

- Python 3.11 или выше
- Node.js 18 или выше
- PostgreSQL 13 или выше
- OpenRouter API key (получить на https://openrouter.ai/keys)

## Установка

### Настройка backend

```bash
cd backend

# Создание и активация виртуального окружения
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Установка зависимостей
pip install -r requirements.txt

# Конфигурация переменных окружения
cp config/env_template.txt .env
# Отредактируйте .env: API-ключи и учётные данные БД

# Инициализация базы данных
./scripts/setup_postgres.sh
./scripts/init_database.sh

# Запуск сервера
make run
```

Backend работает на `http://localhost:8000`

### Настройка frontend

```bash
cd frontend

# Установка зависимостей
npm install

# Запуск dev-сервера
npm run dev
```

Frontend работает на `http://localhost:5173`

### Быстрый старт через Make

Из корня проекта:
```bash
make setup    # Установить все зависимости
make dev      # Запустить backend и frontend
make test     # Запустить тесты
```

## Конфигурация

### Переменные окружения

**Backend** (`.env` в директории backend):
```env
# API-ключи
OPENROUTER_API_KEY=your_openrouter_key

# База данных
DATABASE_URL=postgresql://user:password@localhost:5432/nooversight

# Сервер
HOST=0.0.0.0
PORT=8000
CORS_ORIGINS=http://localhost:5173

# Опционально
LOG_LEVEL=INFO
MAX_SUB_AGENTS=3
```

**Frontend** (зависит от окружения):
- Development: Vite-прокси настроен автоматически
- Production: задать `VITE_API_BASE_URL`

## Структура проекта

```
backend/
├── src/
│   ├── agents/          # Реализация агентов
│   ├── api/             # FastAPI-роуты
│   ├── core/            # Бизнес-логика
│   ├── infrastructure/  # БД, логирование, трекинг
│   ├── tools/           # Реализация инструментов
│   └── app.py          # Точка входа приложения
├── tests/              # Тесты
└── scripts/            # Скрипты настройки БД

frontend/
├── src/
│   ├── components/     # React-компоненты
│   ├── hooks/          # Кастомные хуки
│   ├── services/       # API-клиенты
│   ├── store/          # Управление состоянием
│   ├── styles/         # CSS-модули
│   └── types/          # TypeScript-определения
└── dist/              # Production-сборка
```

## Справочник API

### Основные эндпоинты

**POST** `/api/tasks/execute`
Выполнить задачу с опциональной коллаборацией агентов.

Запрос:
```json
{
  "message": "string",
  "enable_collaboration": boolean,
  "max_sub_agents": number
}
```

**GET** `/api/conversations/{id}`
Получить историю диалога.

**POST** `/api/conversations/{id}/messages`
Добавить сообщение в существующий диалог.

**GET** `/api/settings`
Получить системные настройки и конфигурации моделей.

**GET** `/health`
Health check со статусом сервисов.

### WebSocket

**WS** `/ws`
Двунаправленная связь в реальном времени для стриминга ответов.

## Использование

### Базовое выполнение задачи

```python
import requests

response = requests.post(
    "http://localhost:8000/api/tasks/execute",
    json={
        "message": "Analyze market trends for Q4",
        "enable_collaboration": True
    }
)
```

### Стриминг через SSE

```javascript
const eventSource = new EventSource('/api/tasks/stream');
eventSource.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log(data);
};
```

## Разработка

### Запуск тестов

```bash
# Backend-тесты
cd backend
source venv/bin/activate
pytest

# Frontend-тесты
cd frontend
npm test
```

### Управление базой данных

```bash
# Сброс БД
cd backend
./scripts/reset_database.sh

# Создание миграции
alembic revision --autogenerate -m "description"

# Применение миграций
alembic upgrade head
```

### Качество кода

```bash
# Линтинг backend
cd backend
make lint

# Линтинг frontend
cd frontend
npm run lint
```

## Деплой

### Backend

```bash
cd backend
pip install -r requirements.frozen.txt
uvicorn src.app:app --host 0.0.0.0 --port 8000 --workers 4
```

### Frontend

```bash
cd frontend
npm run build
# Деплой директории dist/ на статический хостинг
```

### Docker (если применимо)

```bash
docker-compose up -d
```

## Расширение системы

### Добавление новых агентов

1. Определить тип агента в `backend/src/core/models.py`
2. Настроить маппинг моделей в `backend/src/agents/agent_factory.py`
3. Обновить типы frontend в `frontend/src/types/index.ts`

### Добавление новых инструментов

1. Создать класс инструмента в `backend/src/tools/`
2. Реализовать интерфейс `BaseTool`
3. Зарегистрировать в `backend/src/tools/registry.py`

### Кастомное поведение агентов

Модифицируйте system prompts и параметры в:
- `backend/src/agents/agent_factory.py` — конфигурация агентов
- `backend/src/core/orchestrator/task_orchestrator.py` — логика оркестрации

## Устранение неполадок

**Ошибки подключения к БД**: проверьте, что PostgreSQL запущен и учётные данные в `.env` корректны

**Ошибки API-ключей**: убедитесь, что все необходимые API-ключи заданы в `.env` backend'а

**Конфликты портов**: измените `PORT` в `.env` backend'а или `vite.config.ts` для frontend'а

**Проблемы с WebSocket**: проверьте настройки CORS и что backend запущен

**Ошибки установки пакетов**: используйте `requirements.frozen.txt` для точных версий зависимостей

## Производительность

- Пул соединений БД настроен на 20 одновременных подключений
- Трекинг token usage для мониторинга затрат на API
- Кэширование истории диалогов
- Параллельное выполнение агентов для ускорения ответа

## Безопасность

- API-ключи хранятся в переменных окружения
- CORS настроен на конкретные origins
- Защита от SQL-инъекций через SQLAlchemy ORM
- Валидация входных данных через Pydantic-модели

## Лицензия

MIT License. Подробности в файле LICENSE.

## Поддержка

Для issue и feature-requests используйте GitHub issue tracker.
