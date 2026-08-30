# Сводный отчёт по фронтенду: технологии и библиотеки во всех 6 проектах

> Дата: 30.08.2026
> Источники: `agents_docs/<проект>/06_frontend_report.md` (по каждому проекту) + проверка
> реальных `package.json`, шаблонов и статики в рабочих деревьях проектов.
> Формат: сравнительный обзор — что используется, чем проекты похожи и чем отличаются.

---

## 1. Резюме: одна картинка на все 6 проектов

Проекты делятся на **три чётких лагеря** по подходу к фронтенду:

| Лагерь | Проекты | Суть подхода |
|---|---|---|
| **SSR/MPA + ванильный JS** | AI-Chatbot, GroqStreamChain | HTML генерирует сервер (Jinja2), клиентский JS — отдельные `<script>`-файлы, без сборщика и npm |
| **Сервер-центричный гибрид (HTMX)** | openai-responses-python-quickstart | HTML генерирует сервер (Jinja2), но частичные обновления DOM делает HTMX; сервер всегда отдаёт HTML-фрагменты, а не JSON |
| **SPA на React + Vite** | llm-council-karpathy, Quorum, rag-knowledge-base-chatbot | Сервер отдаёт JSON/события, весь UI строит React в браузере; сборка через Vite, зависимости через npm |

Сводная таблица стеков:

| Критерий | AI-Chatbot | GroqStreamChain | LLM Council | OpenAI Responses | Quorum | RAG Chatbot |
|---|---|---|---|---|---|---|
| **Подход** | SSR/MPA | SSR/MPA (гибрид) | SPA (CSR) | SSR + HTMX | SPA (CSR) | SPA (CSR) |
| **UI-слой** | HTML + vanilla JS | HTML + vanilla JS | React 19 | Jinja2 + HTMX + vanilla JS | React 18 + TypeScript | React 19 + TypeScript |
| **Шаблонизатор** | Jinja2 | Jinja2 (вхолостую, шаблон статичен) | нет | Jinja2 (полноценный, с компонентами) | нет | нет |
| **Сборщик** | нет | нет | Vite 7 | нет (vendor-скрипты + CDN) | Vite 5 | Vite 7 |
| **Типизация** | нет | нет | нет (JSX) | нет | TypeScript 5.5 (strict) | TypeScript ~5.9 (strict) |
| **Стили** | Tailwind CSS через **CDN** (runtime-компиляция) | чистый CSS | чистые CSS-файлы | чистый CSS (1107 строк) | Tailwind 3 + PostCSS + кастомные классы | Tailwind 4 (`@theme`, Vite-плагин) |
| **Состояние** | нет (один запрос) | локальные переменные | `useState` в `App.jsx` | нет (сервер-центрично) | Zustand 4 (7 slices, persist) | React Context + `useState` |
| **Транспорт** | `fetch` POST | WebSocket `ws://…/ws/chat` | SSE (ручной парсер на `fetch` + `ReadableStream`) | SSE через HTMX (`sse.js`) + AJAX HTML | WebSocket (основной) + SSE (fallback) | axios + `fetch`-стриминг SSE |
| **Markdown-рендер** | нет (только вывод текста) | самодельный regex для ```-блоков | react-markdown 10 | marked.js (CDN) + DOMPurify | react-markdown 10 + remark-gfm 4 | нет (plain text / debug-JSON) |
| **XSS-защита** | ❌ `innerHTML` без санитизации | ❌ `innerHTML` без санитизации | ⚠️ react-markdown (без rehype-raw — относительно безопасно) | ✅ DOMPurify | ⚠️ react-markdown | n/a |
| **Роутинг** | серверный (FastAPI) | нет | нет (один экран) | серверный (FastAPI) | нет (один экран) | react-router-dom 7 (14 страниц) |
| **HTTP-клиент** | fetch | WebSocket | fetch (свой `api.js`) | HTMX + fetch | свой `APIService` + WebSocketService | axios + fetch |
| **Анимации** | CSS | CSS (@keyframes) | CSS | CSS | Framer Motion 11 + GLSL/WebGL фон | CSS (Tailwind-токены) |
| **npm-зависимости** | 0 | 0 | 3 (react, react-dom, react-markdown) | 0 | 8 + dev-набор | 7 + dev-набор |
| **Тесты фронтенда** | нет | нет | нет | нет | нет | нет |
| **Деплой статики** | отдаёт FastAPI | отдаёт FastAPI | dev-сервер Vite (порт 5173) | отдаёт FastAPI | dev-сервер Vite | multi-stage Docker (node → nginx) |

---

## 2. Проект 1 — AI-Chatbot: минимальный SSR

### Стек
- **Jinja2** (через `Jinja2Templates` из Starlette/FastAPI) — 4 шаблона: `landing.html`, `index.html`, `login.html`, `signup.html`.
- **Vanilla JavaScript** — точечные `<script>`-блоки: отправка формы чата через `fetch POST /api/chat`, анимации.
- **Tailwind CSS через CDN** (`<script src="https://cdn.tailwindcss.com">`) — runtime-компиляция стилей в браузере (~300 КБ JS), без сборки.
- Визуальный стиль — **glassmorphism** (полупрозрачные карточки, blur).
- **0 npm-зависимостей**, нет `package.json`, нет сборщика, нет TypeScript.

### Ключевые особенности
- Классический MPA: каждый переход — полная перезагрузка страницы.
- Один запрос → один ответ; нет истории, стриминга и клиентского состояния.
- Шаблоны Jinja2 используются статически (контекст — только `request`).

### Слабые места
- **XSS через `innerHTML`** при вставке ответа модели.
- Tailwind-CDN непригоден для продакшена (медленно, ~300 КБ на каждую загрузку).
- Нет тестов, нет CI, `model` и `base_url` захардкожены.

---

## 3. Проект 2 — GroqStreamChain: SSR + WebSocket-стриминг на чистом JS

### Стек
- **Jinja2** — один шаблон `templates/index.html`, причём **ни одного Jinja2-тега**: шаблон полностью статичный, шаблонизатор используется «по инерции типового паттерна FastAPI».
- **Vanilla JavaScript** — один монолит `static/js/main.js` (240 строк): WebSocket-клиент, отправка сообщений, стриминг, авто-переподключение.
- **Чистый CSS** (`static/css/style.css`): flexbox, чат-пузыри, typing-индикатор на `@keyframes`.
- **0 npm-зависимостей**, нет сборщика.

### Ключевые особенности
- **WebSocket** — главная технология: JSON-фреймы с полем `type` (`session_id`, `initial_message`, `message_received`, `stream`, `stream_end`, `error`); протокол выбирается автоматически `ws://`/`wss://`.
- **Exponential backoff** при переподключении: 2→4→8→10→10 с, до 5 попыток.
- Стриминг-рендеринг: каждый чанк дописывается в пузырь ассистента (пересборкой `innerHTML`).
- Фактически **гибрид**: страница отдаётся через SSR, но весь чат — ручной императивный DOM-код, как в SPA, но без фреймворка.

### Слабые места
- **XSS через `innerHTML`** (контент LLM вставляется как есть).
- Пересборка `innerHTML` на каждый чанк — деградация на длинных ответах.
- Самодельный «мини-markdown» только для блоков кода (regex), без `marked`/`DOMPurify`.
- `sessionId` пишется в `localStorage`, но нигде не используется (мёртвый код).

---

## 4. Проект 3 — llm-council-karpathy: минимальная SPA на React 19

### Стек (проверено по `frontend/package.json`)
- **React 19** + **react-dom 19** — единственные runtime-зависимости, плюс **react-markdown 10**.
- **Vite 7** + `@vitejs/plugin-react` — dev-сервер (порт 5173) и production-сборка.
- **ESLint 9** (flat config) + `eslint-plugin-react-hooks` + `eslint-plugin-react-refresh`.
- **Чистые CSS-файлы** (`index.css`, `App.css`, `components/*.css`) — никаких Tailwind/CSS-модулей.
- **JSX, без TypeScript**. Всего 3 npm-зависимости.

### Архитектура
- Классическая SPA: `index.html` → `<div id="root">` → `main.jsx` (`createRoot` + `StrictMode`).
- **Один источник состояния** — `useState` в `App.jsx` (без Redux/Zustand — приложение маленькое).
- Компоненты-«дураки»: `Sidebar`, `ChatInterface`, `Stage1/2/3` — только `props` + колбэки.
- **SSE без библиотек**: `api.js` читает `response.body.getReader()` (Streams API), декодирует чанки и парсит строки `data: {...}` вручную. Известная слабость — строки могут быть разрезаны между сетевыми чанками.
- **Optimistic UI**: сообщение пользователя появляется мгновенно; каркас ответа совета наполняется по событиям `stage1_start/complete` … `complete`.
- Клиентская **деанонимизация** рецензий (Stage 2): замена «Response X» → имя модели происходит в браузере.

### Слабые места
- Мутация объектов внутри `setCurrentConversation(prev => …)` — нарушение иммутабельности (работает, но техдолг).
- `metadata` (рейтинги, label_to_model) не сохраняется на сервере — теряется после перезагрузки.
- Single-turn UI: форма ввода исчезает после первого вопроса.
- Хрупкий ручной SSE-парсер.

---

## 5. Проект 4 — openai-responses-python-quickstart: HTMX-гипермедиа

### Стек
- **Jinja2** — полноценный серверный рендеринг: `layout.html` + 3 страницы + **13 компонентов** в `templates/components/` (`assistant-run.html`, `user-message.html`, `mcp-approval-request.html`, `weather-widget.html` и др.). Один и тот же шаблон работает и при первой загрузке, и как HTMX/SSE-фрагмент.
- **HTMX** (`static/htmx.min.js`, ~14 КБ, vendor) + **расширение `sse.js`** — AJAX и SSE-стриминг через HTML-атрибуты (`hx-post`, `hx-target`, `hx-swap`, `sse-connect`, `sse-swap`, `hx-swap-oob`).
- **Vanilla JS** — два кастомных файла: `stream-md.js` (343 строки: парсинг OOB-HTML через `DOMParser`, накопительный Markdown в `WeakMap`, рендер) и `audio-recorder.js` (129 строк, IIFE: `MediaRecorder` → `POST /audio/transcribe`).
- **marked.js + DOMPurify** через CDN — единственные внешние библиотеки, и **единственный проект с правильной санитизацией HTML**.
- **Чистый CSS** (`styles.css`, 1107 строк), SVG-иконки inline. **0 npm-зависимостей**, нет сборщика.

### Ключевые особенности — единственный проект в стиле «hypermedia systems»
- **Сервер всегда возвращает HTML, а не JSON.** JSON на клиенте не парсится вообще.
- ~12 типов SSE-событий: простые (`toolOutput`, `imageOutput`, `fileOutput`) обрабатывает стандартный HTMX swap; сложные (`textDelta`, `toolDelta`, `textReplacement`) перехватывает `handleCustomSseEvents()` и отменяет стандартный swap (`evt.preventDefault()`).
- **OOB swap** (out-of-band) — сервер в одном событии обновляет конкретное сообщение ассистента.
- `WeakMap` (DOM-элемент → накопленный Markdown) — автоочистка сборщиком мусора, нет утечек.
- Голосовой ввод через `MediaRecorder` API.

### Слабые места
- Нет auth, path traversal/IDOR в file endpoints (серверная часть).
- CDN-зависимости (marked/DOMPurify) — нет фиксации версий локально (vendor только htmx/sse).
- Ограниченная клиентская логика — при state-heavy UI пришлось бы переписывать на React.

---

## 6. Проект 5 — Quorum: «взрослая» SPA на React 18 + TypeScript

### Стек (проверено по `frontend/package.json`)
- **React 18.3** + **TypeScript 5.5** (strict) + **Vite 5** (esbuild в dev, Rollup в prod; алиас `@` → `./src`, dev-прокси `/api` → `:8000`).
- **Zustand 4** — глобальное состояние: **7 slices** (conversation, messages, agents, ui, stream, settings, history), **нормализованный state** (`byId`/`allIds`), `persist` в localStorage + `devtools`.
- **Tailwind CSS 3** + PostCSS/autoprefixer + кастомные классы в `index.css`.
- **Framer Motion 11** — анимации (`AnimatePresence` в панели агентов).
- **react-markdown 10 + remark-gfm 4** — рендер ответов, `memo` по content.
- **jsPDF 3** — экспорт ответов в PDF; **lucide-react** — иконки.
- **WebGL/GLSL-шейдеры** (`src/shaders/`) — анимированный фон (`GLSLBackground`).
- Кастомный **Logger** с транспортами (Console + Remote с батчингом) и performance-tracking.

### Архитектура — самый сложный фронтенд из шести
- Полное разделение слоёв: `components/` (15+), `hooks/` (`useWebSocket`, `useLogger`), `services/` (API, WebSocket, Logger), `store/`, `types/`, `utils/`, `shaders/`.
- **Event sourcing**: все 20+ типов WS-событий проходят через единственный `streamSlice.handleStreamEvent(event)` → `switch(event.type)` → мутации слайсов.
- **WebSocket-сервис** — класс-синглтон: auto-reconnect (до 10 попыток, backoff), heartbeat ping/pong каждые 30 с, ре-подписки после переподключения, таймаут соединения 10 с.
- **Двойная персистентность**: Zustand `persist` → `localStorage` (ключ `quorum-store`, `partialize` исключает эфемерное состояние) + `sessionStorage` для сообщений активного диалога.
- `ErrorBoundary`, глобальные `window.onerror`/`unhandledrejection`, защита от «опоздавших» событий после завершения стрима.
- SSE-фолбэк (`APIService.streamTask`) существует, но фактически не используется.

### Слабые места
- Нет тестов вообще (план — vitest в roadmap).
- Каждый токен → `set()` → потенциальный ре-рендер; нет батчинга WS-событий.
- Нет виртуализации списка сообщений (`react-window`/`@tanstack/react-virtual` рекомендованы).
- Синхронный PDF-экспорт (jsPDF) может фризить main thread.
- «Обфускация» API-ключа через `btoa` — не шифрование.

---

## 7. Проект 6 — rag-knowledge-base-chatbot: SPA-админка на React 19 + TS + Tailwind 4

### Стек (проверено по `frontend/package.json`)
- **React 19** + **TypeScript ~5.9** (strict) + **Vite 7**.
- **Tailwind CSS 4** — новый способ подключения: как **Vite-плагин** (`@tailwindcss/vite`), дизайн-токены через `@theme` в CSS (тёмная «glass»-тема). Это отличие от Quorum (Tailwind 3 + PostCSS) и AI-Chatbot (Tailwind CDN).
- **axios 1.13** — HTTP-клиент (интерцепторы: Bearer-токен, человекочитаемые ошибки из `detail`).
- **react-router-dom 7** — роутинг на 14 страниц (Dashboard, Conversations, Documents, Crawler, Tickets, Settings, ApiTokens, ApiReference…).
- **lucide-react** — иконки.
- **Деплой**: multi-stage Dockerfile (node:20 build → nginx:alpine), `nginx.conf` со SPA-фолбэком (`try_files … /index.html`) и прокси `/v1` → `api:8000`. Единственный проект с production-деплоем фронтенда.

### Ключевые особенности
- Это **админ-консоль**, а не пользовательский чат: публичный виджет вне репозитория.
- **Auth через React Context** (`AuthContext`): `POST /auth/login` → токен в `localStorage` (ключ `support_ai_token`), проверка `GET /auth/me` при старте, возможность отключить auth через env.
- **Единый API-слой** (`src/api/client.ts`): axios-инстанс + полностью типизированные интерфейсы ответов (1:1 с Pydantic-схемами бэкенда) + запасная авторизация `X-API-Key`.
- **Стриминг SSE** — через **нативный `fetch`** (не axios): `reader.read()`, буфер, разбиение по `\n\n`, парсинг `data:`-строк (события `content`/`done`).
- **Debug-панель (FlowDebugPanel)** — уникальная фича: визуализация внутренностей RAG-пайплайна (решение, confidence, метрики ретрива BM25/vector/rerank, evidence-чанки, превью промптов, лог LLM-вызовов с токенами и стоимостью).

### Слабые места
- Нет тестов (рекомендация — Vitest + Testing Library + Playwright).
- Дублирование паттерна `loading/error/data` на страницах (напрашивается TanStack Query).
- Раздутые страницы: `ConversationDetail.tsx` (669 строк), `Settings.tsx` (601 строка).
- Токен в `localStorage` — уязвим к XSS; тёмная тема захардкожена.

---

## 8. Сравнительный анализ: в чём схожесть и разница

### 8.1. Сходства

1. **Бэкенд везде FastAPI (Python)** — фронтенд всегда общается с FastAPI; различается только формат ответа: HTML (SSR-проекты), JSON+SSE (SPA-проекты), HTML-фрагменты+SSE (HTMX).
2. **Стриминг ответа LLM — общий паттерн для 5 из 6 проектов** (нет его только в AI-Chatbot). При этом технологии разные:
   - WebSocket: GroqStreamChain (единственный чистый WS на клиенте), Quorum (WS основной + SSE fallback);
   - SSE: LLM Council (ручной парсер), OpenAI Responses (HTMX sse.js + кастомный JS), RAG Chatbot (fetch + ручной парсер).
3. **Автоскролл чата и Enter=отправка / Shift+Enter=перенос строки** — повторяется в 5 проектах.
4. **Exponential backoff при переподключении** — GroqStreamChain (5 попыток) и Quorum (10 попыток + heartbeat).
5. **Ни в одном проекте нет тестов фронтенда** — общий техдолг.
6. **CSS-анимации «печатает…»** (три точки) есть в GroqStreamChain, OpenAI Responses, Quorum, RAG Chatbot.
7. **Иконки**: lucide-react в Quorum и RAG Chatbot; SVG inline в OpenAI Responses и Quorum (логотип).

### 8.2. Ключевые различия

| Ось различия | Как разделяются проекты |
|---|---|
| **Кто рендерит HTML** | Сервер (AI-Chatbot, GroqStreamChain, OpenAI Responses) ↔ браузер (LLM Council, Quorum, RAG Chatbot) |
| **Сборка** | Нет сборки (AI-Chatbot, GroqStreamChain, OpenAI Responses — 0 npm-зависимостей) ↔ Vite (три React-проекта) |
| **Типизация** | Только Quorum и RAG Chatbot типизированы (TypeScript strict); LLM Council — чистый JSX |
| **Глобальное состояние** | От «никакого» (AI-Chatbot) через локальный `useState` (LLM Council) и Context (RAG Chatbot) до Zustand с 7 slices и event sourcing (Quorum) |
| **Tailwind: три разных способа подключения** | CDN runtime (AI-Chatbot) → сборка через PostCSS (Quorum, Tailwind 3) → Vite-плагин + `@theme` (RAG Chatbot, Tailwind 4) — фактически показана эволюция Tailwind |
| **Markdown-рендеринг** | Нет (AI-Chatbot, RAG Chatbot) → самодельный regex (GroqStreamChain) → react-markdown (LLM Council, Quorum) → marked+DOMPurify (OpenAI Responses) |
| **Безопасность HTML на клиенте** | ❌ `innerHTML` без санитизации (AI-Chatbot, GroqStreamChain) → ⚠️ react-markdown без rehype-raw → ✅ DOMPurify (только OpenAI Responses) |
| **Масштаб UI** | 1 экран (GroqStreamChain, LLM Council, Quorum) → 4 страницы (AI-Chatbot) → 4+13 фрагментов (OpenAI Responses) → 14 страниц (RAG Chatbot) |
| **Production-деплой фронтенда** | Только RAG Chatbot имеет полноценный контейнер (nginx + SPA-фолбэк); остальные либо отдают статику FastAPI, либо живут на dev-сервере Vite |

### 8.3. Паттерн «сложность фронтенда ↔ сложность задачи»

Отчёты показывают осознанный выбор стека под масштаб, а не «моду»:

- **AI-Chatbot, GroqStreamChain** — 1 экран, 0 зависимостей: vanilla JS оправдан, но их `innerHTML`-XSS нужно чинить (DOMPurify/textContent — 10 строк кода).
- **OpenAI Responses** — богатая серверная логика (tools, MCP approval, файлы, аудио) при минимуме клиентского состояния: HTMX идеален, потому что «чат — это поток текста», а сервер и так рендерит HTML через Jinja2. Итог: ~470 строк кастомного JS против 2000–5000 у React-аналога.
- **LLM Council** — прототип «vibe-coded»: React 19 с 3 зависимостями, один источник состояния, без роутера и стейт-менеджера.
- **Quorum** — сложный реалтайм-дашборд мульти-агентов: полный «канонический» стек (TS + Zustand + Framer Motion + WS-сервис с heartbeat) — единственный проект, где SPA-стек полностью оправдан.
- **RAG Chatbot** — enterprise-админка на 14 страниц: React + Router + axios + строгая типизация API-контрактов + Docker/nginx — тоже канонический выбор.

### 8.4. Общие рекомендации (сводка из отчётов по проектам)

1. **Всем SSR/vanilla-проектам**: заменить `innerHTML` → `textContent` или добавить DOMPurify; вынести markdown-рендер в `marked` + sanitizer (GroqStreamChain, AI-Chatbot).
2. **AI-Chatbot**: уйти с Tailwind-CDN на сборку (Tailwind CLI или Vite-плагин) — CDN-режим только для прототипов.
3. **LLM Council**: починить ручной SSE-парсер (буферизация строк между чанками) и иммутабельность state; при росте — TypeScript.
4. **Quorum**: vitest + Testing Library, виртуализация списка сообщений, батчинг WS-событий (rAF), PDF-экспорт в Web Worker.
5. **RAG Chatbot**: Vitest/Playwright, `useAsync`/TanStack Query вместо ручного `loading/error`, разбить страницы-монолиты, генерация типов из OpenAPI.
6. **Общее**: покрыть фронтенд тестами — ни один из 6 проектов этого не делает.

---

## 9. Итоговая шкала «от простого к сложному»

```
просто ◄──────────────────────────────────────────────────────► сложно

AI-Chatbot      GroqStreamChain    OpenAI Responses    LLM Council      Quorum           RAG Chatbot
4 шаблона       3 файла, WS        HTMX + SSE +        React 19,        React 18 + TS,   React 19 + TS,
Tailwind CDN    0 зависимостей     marked+DOMPurify    3 зависимости    Zustand+Motion   Router+axios+Docker
0 npm           0 npm              0 npm               Vite 7           Vite 5           Vite 7 + Tailwind 4
```

**Главный вывод:** репозиторий демонстрирует все три парадигмы современного фронтенда на
одном бэкенде (FastAPI): классический SSR, hypermedia (HTMX) и SPA. Схожесть — в
пользовательском сценарии (чат со стримингом LLM), различия — в том, кто и чем рендерит
интерфейс и сколько инфраструктуры для этого привлекается.

---

*Смежные документы: детальные отчёты по каждому проекту — `agents_docs/<проект>/06_frontend_report.md` (для AI-Chatbot — `06_frontend_guide.md` + `07_frontend_project_report.md`).*
