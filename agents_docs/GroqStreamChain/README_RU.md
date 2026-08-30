# GroqStreamChain

Приложение чата в реальном времени с потоковой передачей ответов, построенное на FastAPI, WebSocket и Groq LLM.

## Возможности

- 🚀 Потоковая передача ответов от ИИ в реальном времени
- 💬 Интерфейс чата на базе WebSocket
- 🤖 Работает на Groq LLM (API, совместимый с OpenAI)
- 🎨 Современный адаптивный веб-интерфейс
- 📱 Мобильная версия
- 🔄 Управление сессиями с помощью UUID

## Требования

- Python 3.12 или выше
- API-ключ Groq ([Получить здесь](https://console.groq.com/keys))

## Установка

```bash
# Клонируйте репозиторий
git clone https://github.com/your-username/GroqStreamChain.git
cd GroqStreamChain

# Создайте и активируйте виртуальное окружение
python -m venv venv
source venv/bin/activate  # В Windows: venv\Scripts\activate

# Установите зависимости
pip install -r requirements.txt
# или с помощью uv:
# uv sync
```

## Конфигурация

Создайте файл `.env` в корне проекта:

```env
GROQ_API_KEY=ваш_ключ_groq_api
```

Или отредактируйте `config.py` напрямую, чтобы установить `HOST`, `PORT` и `GROQ_API_KEY`.

## Запуск приложения

```bash
# С помощью uv (рекомендуется)
uv sync
uv run python -m server

# Или напрямую
python server.py
```

Приложение запустится по адресу `http://localhost:8000`.

## API-эндпоинты

| Метод | Эндпоинт | Описание |
|-------|----------|----------|
| GET   | `/`      | Веб-интерфейс |
| WS    | `/ws/chat` | WebSocket-эндпоинт для чата |
| GET   | `/health` | Проверка состояния |

## Структура проекта

```
GroqStreamChain/
├── server.py          # FastAPI приложение, WebSocket-эндпоинт
├── config.py          # Конфигурация (HOST, PORT, API-ключи)
├── system_prompts.py  # Шаблоны системных промптов
├── pyproject.toml     # Зависимости и метаданные проекта
├── models/
│   └── chat.py        # Модели данных ChatSession, Message
├── services/
│   └── llm_service.py # Интеграция с LLM (потоковая передача Groq)
├── static/            # Фронтенд-ресурсы (CSS, JS)
├── templates/
│   └── index.html     # Основной шаблон страницы
└── docs/              # Документация проекта
```

## Документация

Подробную документацию см. в папке `docs/`:

- [Структура проекта](docs/01_project_structure.md)
- [Архитектура](docs/02_architecture.md)
- [Поток выполнения](docs/03_execution_flow.md)
- [Качество кода](docs/04_code_quality.md)
- [Дорожная карта оптимизации](docs/05_optimization_roadmap.md)
- [Отчёт по фронтенду](docs/06_frontend_report.md)

## Лицензия

Этот проект лицензирован под лицензией MIT.
