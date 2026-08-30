# 07 — Отчёт: интеграция с AI-моделями

## 1. Обзор

GroqStreamChain использует ровно один канал взаимодействия с LLM: нативный **Groq SDK** (`groq` пакет), вызываемый из `services/llm_service.py`. Никаких других провайдеров, HTTP-эндпоинтов или SDK в runtime-пути не задействовано.

В коде также инициализирован клиент `langchain_groq.ChatGroq` (`services/llm_service.py:18-23`), но он **нигде не вызывается** — ни `.invoke()`, ни `.stream()` на этом объекте не встречается по всему проекту. Это мёртвый код, унаследованный от более ранней версии архитектуры (подтверждено также в `docs/02_architecture.md`, раздел «Паттерны»). Весь фактический трафик к LLM идёт через `self.client = Groq(...)`.

Несмотря на то что `CLAUDE.md` и `README.md` упоминают "OpenAI SDK (Groq is OpenAI-compatible)", пакет `openai` в коде не импортируется и не используется — используется исключительно официальный `groq` клиент.

---

## 2. Провайдер и доступные модели

### Провайдер

Провайдер **жёстко зашит** — это Groq Cloud API (`api.groq.com`). Абстракции над провайдером нет: `LLMService` напрямую создаёт `Groq(api_key=GROQ_API_KEY)` (`services/llm_service.py:17`). Смена провайдера (например, на OpenAI, Anthropic, локальный сервер) потребовала бы правки кода, а не конфигурации.

Это зафиксировано и как техдолг в `docs/05_optimization_roadmap.md` — предложение ввести интерфейс `LLMProvider` для инъекции разных бэкендов пока не реализовано.

### Выбор модели

Модель задаётся одной строкой в `.env` → `MODEL_NAME` (`config.py:9`) и подставляется как есть в параметр `model=` при вызове Groq API (`services/llm_service.py:74`). Захардкоженного списка допустимых моделей в коде нет — подойдёт **любой model ID, который принимает Groq API** на момент запроса.

Актуальные модели, доступные через Groq (`console.groq.com/docs/models`, проверено на момент написания отчёта):

| Категория | Model ID | Комментарий |
|---|---|---|
| Text (production) | `llama-3.1-8b-instant` | Значение по умолчанию в примере `README.md` |
| Text (production) | `llama-3.3-70b-versatile` | Более крупная модель |
| Text + tools (production) | `openai/gpt-oss-120b` | Reasoning + встроенные tools |
| Text (production) | `openai/gpt-oss-20b` | Меньшая версия gpt-oss |
| Speech-to-text | `whisper-large-v3`, `whisper-large-v3-turbo` | Не используется приложением — оно текстовое |
| Agentic system | `groq/compound`, `groq/compound-mini` | Готовая "система" с веб-поиском и code execution от самого Groq |
| Preview / guard | `openai/gpt-oss-safeguard-20b`, `meta-llama/llama-prompt-guard-2-*`, `qwen/qwen3.6-27b` и др. | Для оценки, не для прод-нагрузки |

Важно: список моделей и их доступность на Groq меняются со временем — актуальный список нужно сверять по `console.groq.com/docs/models`, а не по этой таблице.

---

## 3. Формат общения с нейросетью

Общение происходит в два слоя:

### 3.1. Клиент ↔ сервер (WebSocket, JSON)

Эндпоинт `WS /ws/chat` (`server.py:65`). Сообщения — plain JSON поверх текстовых WebSocket-фреймов.

Сервер → клиент:
```json
{"type": "session_id", "session_id": "..."}
{"type": "initial_message", "content": "Hello! I'm your AI assistant..."}
{"type": "message_received", "status": "processing"}
{"type": "stream", "content": "<очередной чанк текста>"}
{"type": "stream_end", "session_id": "..."}
{"type": "error", "message": "Sorry, there was an error..."}
```

Клиент → сервер:
```json
{"message": "текст пользователя"}
```

### 3.2. Сервер ↔ Groq API

Внутри `generate_response_stream()` (`services/llm_service.py:52-95`):

1. История сообщений сессии (`List[Message]`) конвертируется в формат Groq/OpenAI-style (`role`/`content` словари) через `_convert_to_groq_messages()`.
2. В начало списка вставляется системный промпт из `system_prompts.py`.
3. Синхронный вызов `client.chat.completions.create(..., stream=True)` оборачивается в `asyncio.to_thread`, чтобы не блокировать event loop.
4. Ответ Groq — это итератор чанков (Server-Sent Events под капотом SDK); сервер читает `chunk.choices[0].delta.content` построчно и `yield`-ит наружу как `AsyncGenerator[str, None]`.
5. Каждый `yield` немедленно уходит клиенту как WebSocket-сообщение `{"type": "stream", ...}` — то есть чанки не буферизуются, а сразу транслируются.

**Известный баг в этом потоке** (см. также `docs/02_architecture.md`, шаг 6): `messages.insert(0, system_message)` мутирует **тот самый список**, который хранится в `chat_sessions[session_id].messages`. Так как это происходит на каждый пользовательский запрос, системный промпт накапливается в истории сессии повторно с каждым ходом диалога, а не переиспользуется единожды.

---

## 4. Примеры кода

### Инициализация клиента (`services/llm_service.py:15-23`)
```python
class LLMService:
    def __init__(self):
        self.client = Groq(api_key=GROQ_API_KEY)
        self.langchain_client = ChatGroq(   # инициализирован, но не используется
            groq_api_key=GROQ_API_KEY,
            model_name=MODEL_NAME,
            temperature=LLM_CONFIG["temperature"],
            max_tokens=LLM_CONFIG["max_tokens"],
        )
```

### Стриминговый вызов модели (`services/llm_service.py:71-89`)
```python
completion = await asyncio.to_thread(
    self.client.chat.completions.create,
    model=MODEL_NAME,
    messages=groq_messages,
    temperature=LLM_CONFIG["temperature"],
    max_tokens=LLM_CONFIG["max_tokens"],
    top_p=LLM_CONFIG["top_p"],
    stream=True,
    stop=LLM_CONFIG["stop"],
)

for chunk in completion:
    content = chunk.choices[0].delta.content
    if content:
        yield content
```

### Проброс чанков в WebSocket (`server.py:105-117`)
```python
full_response = ""
async for response_chunk in llm_service.generate_response_stream(chat_sessions[session_id].messages):
    await websocket.send_json({"type": "stream", "content": response_chunk})
    full_response += response_chunk

chat_sessions[session_id].messages.append(Message(role="assistant", content=full_response))
await websocket.send_json({"type": "stream_end", "session_id": session_id})
```

### Автономная проверка ключа/модели вне сервера (`test_groq.py`)
```python
client = Groq(api_key=api_key)
completion = client.chat.completions.create(
    model=os.getenv("MODEL_NAME"),
    messages=[{"role": "user", "content": "Hello, can you hear me?"}],
    temperature=0.7,
    max_tokens=100,
    stream=False,
)
print(completion.choices[0].message.content)
```

---

## 5. Возможности приложения

- Текстовый чат в реальном времени через WebSocket с потоковой выдачей ответа (эффект "печатающегося" текста).
- Хранение истории диалога в рамках одной сессии (`ChatSession.messages`), передаваемой в LLM целиком при каждом запросе — то есть модель видит весь предыдущий контекст сессии.
- Единый статичный системный промпт (`system_prompts.py`), задающий тон ассистента — не настраивается через UI, только правкой кода.
- Конфигурируемые параметры генерации через `.env`/`config.py`: `MODEL_NAME`, `temperature`, `max_tokens`, `top_p`, `stop` (`LLM_CONFIG` в `config.py:12-18`).
- Health-check эндпоинт (`GET /health`) для мониторинга доступности сервера (не проверяет доступность самого Groq API).
- Базовая обработка ошибок LLM-вызова — при исключении сервис возвращает пользователю fallback-сообщение об ошибке вместо падения соединения (`services/llm_service.py:93-95`).

### Чего нет

- Нет tool calling / function calling — даже несмотря на то что `openai/gpt-oss-120b` и `groq/compound` эту возможность поддерживают на стороне Groq.
- Нет персистентного хранилища (Redis/БД) — история чата живёт только в памяти процесса и теряется при рестарте.
- Нет RAG, нет векторного поиска, нет вложений/файлов, нет голосового ввода (хотя Groq предоставляет Whisper).
- Нет настройки модели/параметров через UI — только через `.env`.

---

## 6. Мультиагентное использование

**Сейчас не реализовано.** В приложении есть ровно один LLM-вызов на один пользовательский запрос, один системный промпт, один клиент (`LLMService`), создаваемый как синглтон на уровне модуля (`server.py:30`). Оркестрации нескольких агентов, ролей или цепочек вызовов в коде нет.

Технически база для мульти-агентности **частично заложена, но не задействована**:

- В зависимостях уже присутствует `langchain` + `langchain-groq` (`requirements.txt`), которые поддерживают построение мультиагентных графов (например, через LangGraph) — но сам `ChatGroq`-клиент, как отмечено выше, сейчас мёртвый код.
- Groq предоставляет готовую агентную "систему" `groq/compound` (веб-поиск + выполнение кода как встроенные инструменты) — её можно подключить, просто указав `MODEL_NAME=groq/compound`, без агентного фреймворка в приложении. Это не мультиагентность в классическом смысле (несколько независимых LLM-ролей), а один managed-агент от самого провайдера.
- Реализация настоящей мультиагентности (например, "роутер-агент → агент-исследователь → агент-редактор") потребовала бы: (1) вынести интерфейс провайдера/вызова модели в абстракцию (см. предложение `LLMProvider` в `docs/05_optimization_roadmap.md`), (2) добавить оркестрационный слой (LangGraph, CrewAI, ручной state machine), (3) расширить протокол WebSocket, чтобы передавать клиенту, какой агент сейчас отвечает.

---

## 7. Соответствие заявленному в `CLAUDE.md`/`README.md`

- `CLAUDE.md` упоминает "OpenAI SDK (Groq is OpenAI-compatible)" как часть стека — в реальном коде пакет `openai` не используется, используется нативный `groq` SDK. Это несоответствие в документации, не в приложении.
- Единственный поддерживаемый провайдер на сегодня — Groq. Утверждение "какие провайдеры можно использовать" в множественном числе на практике сводится к одному провайдеру и произвольному model ID внутри него.
