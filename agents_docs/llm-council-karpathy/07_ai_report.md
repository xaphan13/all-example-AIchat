# 07 — Отчёт по работе приложения с моделями AI

> Документ описывает всё, что связано с интеграцией LLM в проект **LLM Council**: как приложение общается с нейросетями, примеры реального кода, список возможностей, вопрос мультиагентного использования, поддерживаемые модели и провайдеры.
>
> Материал основан исключительно на коде репозитория: `backend/config.py`, `backend/openrouter.py`, `backend/council.py`, `backend/main.py`, `backend/storage.py`, а также на `AGENTS.md`.

---

## Содержание

1. [Общая картина: что делает приложение](#1-общая-картина)
2. [Архитектура: где и как вызываются LLM](#2-архитектура-слоёв)
3. [В каком виде происходит общение с нейронками](#3-формат-общения-с-нейронками)
4. [Детальный разбор трёх стадий совета](#4-три-стадии-совета)
5. [Примеры кода, работающего с AI](#5-примеры-кода)
6. [Какие модели и провайдеры можно использовать](#6-модели-и-провайдеры)
7. [Возможно ли мультиагентное использование](#7-мультиагентность)
8. [Возможности приложения](#8-возможности-приложения)
9. [Ограничения и известные нюансы](#9-ограничения)
10. [Шпаргалка «где что искать»](#10-шпаргалка)

---

## 1. Общая картина

**LLM Council** — локальное веб-приложение «совет из LLM». Идея: пользователь задаёт один вопрос, несколько нейросетей отвечают на него параллельно (Стадия 1), затем эти же нейросети анонимно рецензируют и ранжируют ответы друг друга (Стадия 2), а отдельная модель-«председатель» синтезирует единый финальный ответ (Стадия 3).

Главный замысел — **анонимизация на стадии рецензирования**: модели видят чужие ответы только под метками `Response A / Response B / ...`, поэтому не могут «подсуживать» конкретным моделям. Реальное соответствие «метка → модель» (`label_to_model`) хранится отдельно и раскрывается только на клиенте, для отображения.

Взаимодействие с AI строится на **одном внешнем сервисе — OpenRouter API** (единый шлюз к моделям OpenAI, Anthropic, Google, xAI и др.). Внутри проекта LLM-запросы выполняются только в трёх местах:

| Где | Функция | Роль моделей |
|---|---|---|
| `council.py` → `stage1_collect_responses()` | 4 модели параллельно отвечают на вопрос | «Рядовые члены совета» |
| `council.py` → `stage2_collect_rankings()` | те же 4 модели параллельно рецензируют анонимные ответы | «Рецензенты» |
| `council.py` → `stage3_synthesize_final()` | 1 модель синтезирует финальный ответ | «Председатель» |
| `council.py` → `generate_conversation_title()` | 1 быстрая модель придумывает заголовок диалога | «Секретарь» (фоновая задача) |

---

## 2. Архитектура слоёв

Зависимости направлены сверху вниз, все вызовы LLM идут через OpenRouter Chat Completions API:

```
main.py (FastAPI, HTTP-роуты, SSE-стриминг)
    │
    ▼
council.py (оркестрация 3 стадий, промпты, парсинг рейтингов, агрегация)
    │
    ▼
openrouter.py (HTTP-клиент: query_model, query_models_parallel)
    │
    ▼
OpenRouter API  https://openrouter.ai/api/v1/chat/completions
```

- `main.py` — REST + SSE эндпоинты; ничего напрямую моделям не отправляет.
- `council.py` — вся «советская» логика: строит промпты, распараллеливает запросы, разбирает ответы.
- `openrouter.py` — единственное место, где реально уходит HTTP-запрос к LLM.
- `storage.py` — персистентность диалогов в JSON, к AI не обращается.

Ключевой принцип — **строгая последовательность стадий** (Stage 2 не начнётся, пока не закончилась Stage 1), но **внутри стадии запросы выполняются параллельно** через `asyncio.gather`.

---

## 3. Формат общения с нейронками

### 3.1. Транспорт

- **Протокол:** обычный HTTPS `POST`.
- **Эндпоинт:** `https://openrouter.ai/api/v1/chat/completions` (задан в `config.py`, константа `OPENROUTER_API_URL`).
- **Формат:** совместим с OpenAI Chat Completions: `{"model": "...", "messages": [{"role": "...", "content": "..."}]}`.
- **Авторизация:** заголовок `Authorization: Bearer <OPENROUTER_API_KEY>`. Ключ берётся из переменной окружения `OPENROUTER_API_KEY` (файл `.env`, загрузка через `python-dotenv` в `config.py`).
- **Библиотека:** `httpx` (асинхронный клиент, `AsyncClient`).
- **Таймаут:** по умолчанию 120 секунд (`timeout: float = 120.0`); для генерации заголовка — 30 секунд.

### 3.2. Структура запроса

```json
{
  "model": "openai/gpt-5.1",
  "messages": [
    {"role": "user", "content": "Расскажи про LLM Council"}
  ]
}
```

**Важный нюанс:** системные промпты (`role: "system"`) не используются вовсе. Все инструкции (роль, задача, формат ответа) вшиваются прямо в текст сообщения `role: "user"`. Это видно по всем промптам в `council.py`.

### 3.3. Структура ответа (что берёт приложение)

Из JSON-ответа извлекается только `data['choices'][0]['message']`, откуда берутся:

- `content` — текст ответа модели (всегда);
- `reasoning_details` — необязательное поле «рассуждений» (если провайдер/модель его отдаёт).

Всё остальное (токены, usage и пр.) игнорируется.

### 3.4. Обработка ошибок и деградация

```python
try:
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(...)
        response.raise_for_status()
        ...
except Exception as e:
    print(f"Error querying model {model}: {e}")
    return None
```

- Любая ошибка модели (сеть, 4xx/5xx, пустой ответ) → возвращается `None`.
- `stage1_collect_responses()` пропускает упавшие модели и формирует список только из успешных ответов.
- Если упали **все** модели — стадия 1 возвращает пустой список, и `run_full_council()` сразу возвращает ошибку пользователю («All models failed to respond»).
- Если упал «председатель» — возвращается заглушка «Error: Unable to generate final synthesis».
- Если упала генерация заголовка — заголовок становится `"New Conversation"`.

Запрос пользователя **никогда не теряется** из-за сбоя одной модели: это принцип graceful degradation.

---

## 4. Три стадии совета

### Стадия 1 — индивидуальные ответы (`stage1_collect_responses`)

1. Формируется сообщение `{"role": "user", "content": user_query}`.
2. `query_models_parallel(COUNCIL_MODELS, messages)` отправляет его **всем членам совета одновременно**.
3. Из ответов собирается список `[{model, response}]`, куда попадают только успешные (`response is not None`).

### Стадия 2 — анонимное рецензирование (`stage2_collect_rankings`)

1. Ответам присваиваются анонимные метки: `Response A`, `Response B`, `Response C`, … (по алфавиту, через `chr(65 + i)`).
2. Строится карта `label_to_model = {"Response A": "openai/gpt-5.1", ...}` — она нужна для последующей деанонимизации, но **не передаётся моделям**.
3. Каждой модели отправляется специальный промпт, в котором:
   - приведён оригинальный вопрос;
   - приведены все ответы только под метками `Response X`;
   - задана задача: сначала оценить каждый ответ текстом, затем в самом конце дать **строго отформатированный** рейтинг.
4. Модели рецензируют параллельно. Из ответа:
   - сохраняется полный текст рецензии (`ranking`);
   - регулярным выражением извлекается список меток в порядке ранжирования (`parsed_ranking`).

**Требование к формату рейтинга** (прописано прямо в промпте):

```
FINAL RANKING:
1. Response C
2. Response A
3. Response B
```

Парсинг — `parse_ranking_from_text()`:
- ищет секцию после строки `FINAL RANKING:`;
- вытаскивает из неё строки вида `1. Response A` (регэксп `\d+\.\s*Response [A-Z]`);
- если такого нет — просто собирает все вхождения `Response [A-Z]` по порядку.

**Агрегация** — `calculate_aggregate_rankings()`: для каждой модели собираются позиции во всех рецензиях и считается средний ранг (`average_rank`, чем меньше — тем лучше) плюс количество голосов (`rankings_count`). Это и есть «Street Cred» совета.

### Стадия 3 — синтез председателем (`stage3_synthesize_final`)

1. В один большой промпт собираются: оригинальный вопрос, все индивидуальные ответы **с указанием моделей** (здесь анонимность не нужна) и все рецензии **с указанием моделей**.
2. Промпт отправляется **одной** модели — `CHAIRMAN_MODEL`.
3. Ответ председателя и есть финальный ответ пользователю.

### Фоновая задача — заголовок диалога (`generate_conversation_title`)

- Вызывается только для первого сообщения в диалоге.
- Запускается в фоне (`asyncio.create_task`), параллельно стадии 1.
- Модель `google/gemini-2.5-flash` просится придумать заголовок из 3–5 слов; результат чистится от кавычек и обрезается до 50 символов.
- Выбор именно этой модели закомментирован как «fast and cheap».

### Полная последовательность событий (SSE)

```
POST /api/conversations/{id}/message/stream
  → stage1_start
  → stage1_complete        (data: ответы моделей)
  → stage2_start
  → stage2_complete        (data: рецензии + metadata: label_to_model, aggregate_rankings)
  → stage3_start
  → stage3_complete        (data: финальный ответ)
  → title_complete         (только для первого сообщения)
  → complete
  → error                  (при любом исключении)
```

---

## 5. Примеры кода

### 5.1. Запрос к одной модели — `backend/openrouter.py`

```python
async def query_model(
    model: str,
    messages: List[Dict[str, str]],
    timeout: float = 120.0
) -> Optional[Dict[str, Any]]:
    """Query a single model via OpenRouter API."""
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": model,
        "messages": messages,
    }

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                OPENROUTER_API_URL,
                headers=headers,
                json=payload
            )
            response.raise_for_status()

            data = response.json()
            message = data['choices'][0]['message']

            return {
                'content': message.get('content'),
                'reasoning_details': message.get('reasoning_details')
            }

    except Exception as e:
        print(f"Error querying model {model}: {e}")
        return None
```

### 5.2. Параллельный опрос нескольких моделей

```python
async def query_models_parallel(
    models: List[str],
    messages: List[Dict[str, str]]
) -> Dict[str, Optional[Dict[str, Any]]]:
    """Query multiple models in parallel."""
    import asyncio

    tasks = [query_model(model, messages) for model in models]
    responses = await asyncio.gather(*tasks)

    return {model: response for model, response in zip(models, responses)}
```

### 5.3. Стадия 1 — коллекция ответов

```python
async def stage1_collect_responses(user_query: str) -> List[Dict[str, Any]]:
    messages = [{"role": "user", "content": user_query}]

    # Все модели опрашиваются параллельно
    responses = await query_models_parallel(COUNCIL_MODELS, messages)

    stage1_results = []
    for model, response in responses.items():
        if response is not None:  # только успешные ответы
            stage1_results.append({
                "model": model,
                "response": response.get('content', '')
            })

    return stage1_results
```

### 5.4. Стадия 2 — промпт для анонимного ранжирования

```python
responses_text = "\n\n".join([
    f"Response {label}:\n{result['response']}"
    for label, result in zip(labels, stage1_results)
])

ranking_prompt = f"""You are evaluating different responses to the following question:

Question: {user_query}

Here are the responses from different models (anonymized):

{responses_text}

Your task:
1. First, evaluate each response individually. For each response, explain what it does well and what it does poorly.
2. Then, at the very end of your response, provide a final ranking.

IMPORTANT: Your final ranking MUST be formatted EXACTLY as follows:
- Start with the line "FINAL RANKING:" (all caps, with colon)
- Then list the responses from best to worst as a numbered list
- Each line should be: number, period, space, then ONLY the response label (e.g., "1. Response A")
- Do not add any other text or explanations in the ranking section

Example of the correct format for your ENTIRE response:

Response A provides good detail on X but misses Y...
Response B is accurate but lacks depth on Z...
Response C offers the most comprehensive answer...

FINAL RANKING:
1. Response C
2. Response A
3. Response B

Now provide your evaluation and ranking:"""

messages = [{"role": "user", "content": ranking_prompt}]
responses = await query_models_parallel(COUNCIL_MODELS, messages)
```

### 5.5. Парсинг рейтинга из текста рецензии

```python
def parse_ranking_from_text(ranking_text: str) -> List[str]:
    import re

    if "FINAL RANKING:" in ranking_text:
        parts = ranking_text.split("FINAL RANKING:")
        if len(parts) >= 2:
            ranking_section = parts[1]
            # Ищем нумерованный список вида "1. Response A"
            numbered_matches = re.findall(r'\d+\.\s*Response [A-Z]', ranking_section)
            if numbered_matches:
                return [re.search(r'Response [A-Z]', m).group() for m in numbered_matches]
            # Fallback: все вхождения "Response X" подряд
            return re.findall(r'Response [A-Z]', ranking_section)

    # Fallback: ищем метки по всему тексту
    return re.findall(r'Response [A-Z]', ranking_text)
```

### 5.6. Агрегация рейтингов (Street Cred)

```python
def calculate_aggregate_rankings(stage2_results, label_to_model):
    from collections import defaultdict

    model_positions = defaultdict(list)

    for ranking in stage2_results:
        parsed_ranking = parse_ranking_from_text(ranking['ranking'])
        for position, label in enumerate(parsed_ranking, start=1):
            if label in label_to_model:
                model_positions[label_to_model[label]].append(position)

    aggregate = []
    for model, positions in model_positions.items():
        if positions:
            avg_rank = sum(positions) / len(positions)
            aggregate.append({
                "model": model,
                "average_rank": round(avg_rank, 2),
                "rankings_count": len(positions)
            })

    aggregate.sort(key=lambda x: x['average_rank'])  # меньше — лучше
    return aggregate
```

### 5.7. Стадия 3 — промпт председателя

```python
stage1_text = "\n\n".join([
    f"Model: {result['model']}\nResponse: {result['response']}"
    for result in stage1_results
])

stage2_text = "\n\n".join([
    f"Model: {result['model']}\nRanking: {result['ranking']}"
    for result in stage2_results
])

chairman_prompt = f"""You are the Chairman of an LLM Council. Multiple AI models have provided responses to a user's question, and then ranked each other's responses.

Original Question: {user_query}

STAGE 1 - Individual Responses:
{stage1_text}

STAGE 2 - Peer Rankings:
{stage2_text}

Your task as Chairman is to synthesize all of this information into a single, comprehensive, accurate answer to the user's original question. Consider:
- The individual responses and their insights
- The peer rankings and what they reveal about response quality
- Any patterns of agreement or disagreement

Provide a clear, well-reasoned final answer that represents the council's collective wisdom:"""

messages = [{"role": "user", "content": chairman_prompt}]
response = await query_model(CHAIRMAN_MODEL, messages)
```

### 5.8. Генерация заголовка диалога

```python
async def generate_conversation_title(user_query: str) -> str:
    title_prompt = f"""Generate a very short title (3-5 words maximum) that summarizes the following question.
The title should be concise and descriptive. Do not use quotes or punctuation in the title.

Question: {user_query}

Title:"""

    messages = [{"role": "user", "content": title_prompt}]

    # Быстрая и дешёвая модель для заголовков
    response = await query_model("google/gemini-2.5-flash", messages, timeout=30.0)

    if response is None:
        return "New Conversation"

    title = response.get('content', 'New Conversation').strip()
    title = title.strip('"\'')
    if len(title) > 50:
        title = title[:47] + "..."
    return title
```

### 5.9. Полный пайплайн

```python
async def run_full_council(user_query: str):
    # Стадия 1
    stage1_results = await stage1_collect_responses(user_query)

    # Если все модели упали — сразу ошибка
    if not stage1_results:
        return [], [], {
            "model": "error",
            "response": "All models failed to respond. Please try again."
        }, {}

    # Стадия 2 + агрегация
    stage2_results, label_to_model = await stage2_collect_rankings(user_query, stage1_results)
    aggregate_rankings = calculate_aggregate_rankings(stage2_results, label_to_model)

    # Стадия 3
    stage3_result = await stage3_synthesize_final(user_query, stage1_results, stage2_results)

    metadata = {
        "label_to_model": label_to_model,
        "aggregate_rankings": aggregate_rankings
    }

    return stage1_results, stage2_results, stage3_result, metadata
```

### 5.10. Пример API-запроса из командной строки (как это выглядит «снаружи»)

Ключ — из `.env`, формат — стандартный Chat Completions:

```bash
curl -X POST https://openrouter.ai/api/v1/chat/completions \
  -H "Authorization: Bearer $OPENROUTER_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "openai/gpt-5.1",
    "messages": [{"role": "user", "content": "Расскажи про LLM Council"}]
  }'
```

---

## 6. Модели и провайдеры

### 6.1. Провайдер

Приложение использует **только один внешний провайдер — OpenRouter** (`https://openrouter.ai/api/v1/chat/completions`). Это агрегатор: за одним ключом и одним API-форматом скрываются модели множества вендоров.

Прямых интеграций с API OpenAI/Anthropic/Google и т.д. в коде нет — для этого придётся расширять `openrouter.py`.

### 6.2. Текущий состав совета — `backend/config.py`

```python
# Совет (Stage 1 и Stage 2 — отвечают и рецензируют)
COUNCIL_MODELS = [
    "openai/gpt-5.1",
    "google/gemini-3-pro-preview",
    "anthropic/claude-sonnet-4.5",
    "x-ai/grok-4",
]

# Председатель (Stage 3 — синтез финального ответа)
CHAIRMAN_MODEL = "google/gemini-3-pro-preview"
```

Модель заголовков — `google/gemini-2.5-flash` — захардкожена в `council.py` (а не в конфиге).

### 6.3. Как добавить/сменить модели

Достаточно отредактировать список в `config.py`:

```python
COUNCIL_MODELS = [
    "openai/gpt-5.1",
    "google/gemini-3-pro-preview",
    "anthropic/claude-sonnet-4.5",
    "x-ai/grok-4",
    "meta-llama/llama-4-maverick",   # добавили пятую модель
]
```

Ограничения:
- код не проверяет существование моделей заранее — неудачный идентификатор просто упадёт на стадии запроса и будет пропущен (graceful degradation);
- длина списка не ограничена, но стадии 1–2 опрашивают всех членов **параллельно**, так что время ответа почти не растёт;
- чем больше моделей, тем длиннее промпты стадий 2–3 (все ответы/рецензии складываются в один запрос) — надо следить за лимитом контекста председателя.

### 6.4. Какие модели доступны через OpenRouter

Теоретически — любые, представленные в каталоге OpenRouter. На практике популярны:

| Вендор | Примеры идентификаторов |
|---|---|
| OpenAI | `openai/gpt-5.1`, `openai/gpt-5`, `openai/o3` и др. |
| Anthropic | `anthropic/claude-sonnet-4.5`, `anthropic/claude-opus-4.1` и др. |
| Google | `google/gemini-3-pro-preview`, `google/gemini-2.5-flash` и др. |
| xAI | `x-ai/grok-4`, `x-ai/grok-4-fast` и др. |
| Meta | `meta-llama/llama-4-maverick`, `meta-llama/llama-4-scout` и др. |
| Прочие | DeepSeek, Mistral, Qwen, Cohere и десятки других |

Идентификатор всегда вида `vendor/model-name` — именно так их нужно вписывать в `COUNCIL_MODELS`.

---

## 7. Мультиагентность

**Короткий ответ: да, приложение — по сути мультиагентная (точнее, мультимодельная) система**, но с очень простой моделью кооперации.

### 7.1. Что реализовано

- **Параллелизм:** на каждой стадии несколько моделей работают одновременно (`asyncio.gather`).
- **Ролевая модель:** «рядовые члены» (отвечают + рецензируют) и отдельный «председатель» (синтез). Роли заданы статически в конфиге.
- **Кооперация через промпты:** агенты не общаются напрямую — они обмениваются текстами внутри промптов следующей стадии. Стадия 2 передаёт каждой модели чужие ответы (анонимно), стадия 3 передаёт председателю все ответы и рецензии.
- **Предотвращение сговора:** анонимизация на стадии рецензирования — это, по сути, анти-коллаборация: модели оценивают ответы, не зная их авторов.

### 7.2. Ограничения (чего НЕТ)

- Нет итеративного диалога между агентами — каждая стадия выполняется ровно один раз, «совещание» не имеет раундов.
- Нет у агентов инструментов (tool use), внешней памяти, планирования, self-reflection.
- Нет динамического выбора моделей под задачу — состав совета статичен.
- Нет обмена между моделями в реальном времени — только через промежуточные промпты.
- Председатель не может задать уточняющий вопрос «рядовым».

### 7.3. Направления расширения (если хочется «настоящей» мультиагентности)

1. **Несколько раундов рецензирования** — цикл «ответить → рецензировать → переписать с учётом рецензий» (несколько итераций внутри стадии 1/2).
2. **Роутер задач** — отдельная модель выбирает, каких членов совета и в каком составе опросить под конкретный вопрос.
3. **Инструменты (function calling)** — добавить в `openrouter.py` поддержку `tools` и цикл исполнения.
4. **Динамические роли** — «адвокат дьявола», «эксперт по фактам», «редактор» и т.п. с разными промптами.
5. **Голосование по консенсусу** — если модели сильно расходятся, запускать дополнительный раунд разбирательств.

---

## 8. Возможности приложения

| Возможность | Как реализовано |
|---|---|
| **Коллективный ответ из 3 стадий** | `council.py`: ответы всех моделей → анонимные рецензии → синтез председателя |
| **Параллельная работа моделей** | `query_models_parallel()` + `asyncio.gather` |
| **Анонимное рецензирование** | Метки `Response A/B/C` в промптах стадии 2, карта `label_to_model` отдельно |
| **Агрегированный рейтинг моделей («Street Cred»)** | `calculate_aggregate_rankings()`: средний ранг + число голосов |
| **Парсинг рейтингов из текста** | Регэксп `FINAL RANKING:` → `parse_ranking_from_text()` |
| **Стриминг прогресса по SSE** | `main.py`: события стадий, UI обновляется по мере готовности |
| **Устойчивость к сбоям** | Провал модели → `None` → пропуск; провал всех → понятная ошибка; заглушка при провале председателя |
| **Хранение диалогов** | JSON-файлы (`data/conversations/`), история по ролям с разбивкой по стадиям |
| **Авто-заголовки диалогов** | Фоновая генерация `google/gemini-2.5-flash` для первого сообщения |
| **Гибкая настройка моделей** | Списки в `config.py` (`COUNCIL_MODELS`, `CHAIRMAN_MODEL`) |
| **REST API** | `GET/POST /api/conversations*`, синхронный и стриминговый эндпоинты сообщений |
| **Локальный запуск** | `uv` + `npm`, без баз данных и внешних сервисов (кроме OpenRouter) |

---

## 9. Ограничения

Зафиксированы в коде и в `AGENTS.md`:

1. **Один провайдер.** Только OpenRouter; другие API потребуют доработки `openrouter.py`.
2. **Модели захардкожены** в `config.py` (и `google/gemini-2.5-flash` для заголовков — прямо в `council.py`). Пользователь не выбирает модели в UI.
3. **Стадии строго последовательны** и выполняются один раз; нет итераций и обратной связи.
4. **Метаданные не персистятся.** `label_to_model` и `aggregate_rankings` отдаются только по SSE и не сохраняются в JSON — после перезагрузки страницы деанонимизация и рейтинг теряются.
5. **Парсинг рейтинга хрупкий:** зависит от точного соблюдения модели формата `1. Response A`; регэксп не различает «Response 1»/«Response A» намеренно, но и не защищён от «творческих» отклонений.
6. **Пустой `content` не проверяется** — модель может «ответить» пустотой, и это не будет считаться ошибкой.
7. **Контекст стадий 2–3 растёт** с числом моделей (все ответы и рецензии в одном промпте) — есть потолок по лимиту председателя.
8. **Мультиагентность в простой форме** — только статичные роли и кооперация через промпты (см. раздел 7).

---

## 10. Шпаргалка

| Если нужно... | Идти сюда |
|---|---|
| Поменять состав совета / председателя | `backend/config.py` → `COUNCIL_MODELS`, `CHAIRMAN_MODEL` |
| Сменить ключ API | `.env` → `OPENROUTER_API_KEY` |
| Изменить эндпоинт OpenRouter | `backend/config.py` → `OPENROUTER_API_URL` |
| Поправить HTTP-клиент / таймауты / формат | `backend/openrouter.py` |
| Изменить промпты стадий или логику рейтингов | `backend/council.py` |
| Добавить эндпоинт / изменить SSE-события | `backend/main.py` |
| Понять формат хранения диалогов | `backend/storage.py` + `data/conversations/` |
| Добавить поддержку другого провайдера | `backend/openrouter.py` (новый клиент) + выбор в `council.py` |

---

## Итог

Приложение — это мультимодельный «совет»: несколько LLM параллельно отвечают на вопрос (Stage 1), анонимно рецензируют и ранжируют ответы друг друга (Stage 2), а отдельная модель-председатель синтезирует финальный ответ (Stage 3). Общение с нейросетями — обычные HTTPS-запросы в формате Chat Completions через единственного провайдера OpenRouter; модели задаются списками в `config.py` и могут быть заменены на любые доступные в каталоге OpenRouter. Мультиагентность реализована в простейшей форме (параллелизм + роли + кооперация через промпты + анти-сговор анонимизацией), с чётким потенциалом развития до полноценного агентного оркестратора.
