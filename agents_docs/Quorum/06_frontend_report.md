# 06 — Фронтенд: расширенный отчёт и разбор технологий

> Смешанный отчёт: часть I — образовательный блок о том, как вообще устроен веб-фронтенд
> (React, Vite, Vue, Jinja2 и связанные концепции); часть II — детальный разбор фронтенда
> проекта NoOversight / Quorum.
> Версия: август 2026. Создан по запросу пользователя.

---

## Часть I. Как вообще устроен веб-фронтенд

### 1.1 Базовая модель клиент-сервер

Любое веб-приложение — это диалог двух программ:

```
Браузер (клиент)                    Сервер
   │  GET /  (запрос страницы)         │
   ├─────────────────────────────────→ │
   │  ← HTML + CSS + JS ─────────────┤ │
   │  (дальше JS сам решает,          │ │
   │   что запросить ещё)             │ │
   │  ←── JSON (данные) ────────────→ │ │
```

- **Клиент** — это то, что исполняется в браузере пользователя: HTML (структура), CSS (стили), JavaScript (логика).
- **Сервер** — то, что хранит данные, выполняет тяжёлую работу и отдаёт ответы по HTTP/WebSocket.

Термин **«фронтенд»** означает всю клиентскую часть: вёрстку, интерактивность, логику UI, общение с API.
Термин **«бэкенд»** — серверную часть.

### 1.2 Два фундаментальных подхода: MPA и SPA

**MPA (Multi-Page Application, многостраничное приложение)** — классика:
- Каждая страница — отдельный HTML-документ, который сервер полностью генерирует и отдаёт.
- Переход между страницами = новый запрос к серверу + полная перезагрузка браузера.
- Пример: интернет-магазины, Wikipedia, корпоративные сайты.

**SPA (Single-Page Application, одностраничное приложение)** — современный подход:
- Сервер отдаёт **один** HTML-файл с одним `<div id="root">` и JS-бандлом.
- JavaScript полностью управляет интерфейсом: рисует, перерисовывает, «переключает страницы» без перезагрузки.
- Общение с сервером — через API (JSON) и WebSocket.
- Примеры: Gmail, Figma, Slack, Notion.

Проект **Quorum — классическая SPA**: в `frontend/index.html` один контейнер `#root`,
а весь UI строится кодом на React.

### 1.3 «Сырой» JS против фреймворков

Писать сложный интерфейс на чистом `document.getElementById(...)` — больно: код превращается
в спагетти из манипуляций с DOM. Поэтому придумали **фреймворки** — библиотеки, которые берут на себя
два главных вопроса:

1. **Как описать интерфейс** (декларативно, а не «вручную поменяй этот элемент»).
2. **Как синхронизировать состояние (данные) с тем, что видит пользователь.**

Главные игроки на 2026 год:

| Фреймворк | Фирма | Модель | Когда выбирают |
|---|---|---|---|
| **React** | Meta | Компоненты + виртуальный DOM + односторонний поток данных | Универсальный де-факто стандарт |
| **Vue** | Evan You (сообщество) | Компоненты + реактивные прокси (без виртуального DOM в компилируемом режиме) | Быстрый старт, меньше кривая обучения |
| **Angular** | Google | Полноценный фреймворк (DI, роутер, формы, RxJS) | Крупные enterprise-проекты |
| **Svelte** | Rich Harris | Компилятор: превращает компоненты в чистый JS без runtime | Максимальная скорость, малые бандлы |

### 1.4 React подробно

React — библиотека для построения UI из **компонентов**.

**Компонент** — функция (или класс), которая возвращает «что нарисовать»:

```tsx
function Greeting({ name }: { name: string }) {
  return <h1>Hello, {name}!</h1>;
}
```

Ключевые идеи React:

1. **JSX** — синтаксис, где HTML-подобная разметка живёт прямо в JavaScript/TypeScript-коде.
   JSX **не понимается браузером** — его компилирует сборщик (Vite/esbuild) в обычные вызовы `React.createElement(...)`.

2. **Декларативность.** Вы описываете, *каким* должен быть UI при данном состоянии, а не *как* его поменять.
   Это главное отличие от императивного jQuery-стиля.

3. **Props и State.**
   - `props` — входные данные компонента (неизменяемые, передаются от родителя);
   - `state` — внутренние данные компонента (`useState`), изменение которых вызывает перерисовку.

4. **Виртуальный DOM (Virtual DOM).** При каждом изменении состояния React пересобирает
   «дерево элементов» в памяти (быстро), сравнивает его с предыдущим (reconciliation) и
   точечно патчит только изменившиеся узлы настоящего DOM (медленная операция). Такой подход
   жертвует частью скорости ради простоты разработки.

5. **Односторонний поток данных.** Данные текут сверху вниз (от родителя к детям через props).
   Изменения состояния — через события, которые поднимаются вверх. Это упрощает отладку.

6. **Hooks** — функции для «подключения» к возможностям React внутри функциональных компонентов:
   - `useState` — локальное состояние;
   - `useEffect` — сайд-эффекты (подписки, таймеры, запросы);
   - `useRef` — ссылка на DOM-узел или mutable-значение без перерисовки;
   - `useCallback` / `useMemo` — мемоизация функций и значений;
   - `useStore`/хуки библиотек — подключение к глобальному стору (в проекте — Zustand).

7. **Re-render (перерисовка).** React перерисовывает компонент, когда меняется его state,
   props или контекст. Частые перерисовки — главный источник проблем производительности,
   поэтому используют мемоизацию (`memo`, `useMemo`, селекторы).

В проекте Quorum React используется «в каноническом виде»: функциональные компоненты, хуки,
`memo` для тяжёлых деревьев (`MarkdownRenderer`, `MessageBubble`, `AgentConversation`),
`React.StrictMode` для контроля корректности.

### 1.5 Vite подробно

**Vite** — инструмент разработки и сборки фронтенда («сборщик» / build tool). Заменил
более старые и медленные Webpack/Parcel.

Две его главные роли:

**1. Dev-сервер (режим разработки).**
- Запускается по команде `npm run dev` (в проекте — `vite`, порт 5173).
- Отдаёт браузеру исходники «как есть», почти без сборки: ES-модули грузятся браузером нативно.
- Ключевая фишка — **HMR (Hot Module Replacement)**: при сохранении файла страница **не перезагружается**, а обновляется только изменённый модуль. Состояние приложения сохраняется.
- Зависимости (react, zustand и т.д.) предварительно «пре-ба́ндлятся» через **esbuild** (написан на Go, в десятки раз быстрее Webpack).

**2. Production build.**
- Команда `npm run build` → `tsc && vite build`.
- Vite через **Rollup** собирает все модули в оптимизированные статические файлы
  (минификация, tree-shaking — вырезание неиспользуемого кода, code-splitting, хеши имён файлов для кэширования).
- Результат — папка `dist/`, которую раздаёт любой статический сервер.

**Что умеет Vite из коробки:**
- TypeScript — транспиляция (без проверки типов; её отдельно делает `tsc` в `npm run build`);
- CSS и препроцессоры (в проекте — Tailwind через PostCSS);
- алиасы путей (в проекте `@` → `./src`);
- dev-прокси (в проекте `/api` → `http://localhost:8000` — чтобы не было CORS-проблем при разработке);
- переменные окружения `import.meta.env.VITE_*`.

**Почему это важно для проекта:** фронтенд Quorum не требует сборки в dev-режиме, HMR мгновенно
обновляет компоненты при правках, а production-сборка производится одной командой `npm run build`.

### 1.6 Vue (кратко)

**Vue** — альтернативный фреймворк, тоже компонентный, но с другим подходом:

- Компонент описывается в «одном файле» (SFC, Single File Component): `<template>`, `<script>`, `<style>` в одном `.vue`-файле.
- **Реактивность на основе прокси (Proxy)**: Vue «оборачивает» данные, автоматически отслеживая,
  какие компоненты их читают, и перерисовывает только их — без явного виртуального DOM и reconciliation.
- Прямое сравнение с React:

| Аспект | React | Vue |
|---|---|---|
| Описание UI | JSX (разметка в JS) | `<template>` (HTML + директивы) |
| Реактивность | Через перерисовку компонента + Virtual DOM | Через Proxy-обёртки данных (точные обновления) |
| Кривая обучения | Средняя/высокая (hooks, паттерны) | Низкая (ближе к HTML) |
| Экосистема | Огромная | Большая, но меньше |
| Где применяется | Абсолютно везде | SPA, интранет, лендинги, Nuxt-сайты |

В Quorum Vue не используется — выбран React; понимать Vue полезно для сравнения и для работы
с чужими проектами.

### 1.7 Jinja2 (и почему это «другой мир»)

**Jinja2** — **шаблонизатор** для Python (часть экосистемы Flask/Django/FastAPI-приложений),
а не JavaScript-фреймворк. Он работает **на сервере**:

```jinja2
<!doctype html>
<html>
<head><title>{{ page_title }}</title></head>
<body>
  <h1>Привет, {{ user.name }}!</h1>
  {% if messages %}
    <ul>{% for m in messages %}<li>{{ m }}</li>{% endfor %}</ul>
  {% endif %}
</body>
</html>
```

Как это работает:
1. Серверный код (Python) подготавливает данные (`user`, `messages`).
2. Jinja2 подставляет их в шаблон и генерирует **готовый HTML**.
3. Браузер получает полностью готовую страницу.

Это **MPA-подход**: каждый запрос → рендер на сервере → полная страница в браузере.
JavaScript на таких сайтах используется точечно (анимации, AJAX-запросы), но **не строит весь UI**.

**Почему нельзя просто «сравнить» React и Jinja2?** Это разные слои:
- Jinja2 отвечает за вопрос «как из данных получить HTML на сервере» (SSR-в-стиле-бэкенда).
- React отвечает за вопрос «как интерфейс живёт и реагирует на действия пользователя в браузере» (CSR).

В реальном мире часто встречается гибрид: Jinja2 (или другой серверный рендер) отдаёт каркас страницы,
а React-компоненты «монтируются» в отдельные контейнеры. В Quorum такого гибрида нет — фронтенд
полностью на React, бэкенд (FastAPI) отдаёт только JSON и WebSocket-события.

### 1.8 Ещё несколько терминов из экосистемы

| Термин | Что это |
|---|---|
| **TypeScript** | Надстройка над JS со статическими типами. Компилируется в JS. Даёт автодополнение и ловит ошибки на этапе разработки (`tsc` в `npm run build`). |
| **Tailwind CSS** | CSS-фреймворк «utility-first»: вместо именованных классов (`btn`) пишут утилиты прямо в JSX (`px-3 py-1 rounded`). Компилируется PostCSS-плагином, вырезая неиспользуемые стили. |
| **Zustand** | Лёгкая библиотека управления глобальным состоянием для React (альтернатива Redux). Хранилище — обычный JS-объект вне компонентов + хук `useStore`. |
| **Redux** | Тяжёлая классика управления состоянием: actions → reducers → store. В Quorum заменён Zustand. |
| **React Query / TanStack Query** | Библиотека для кэширования серверных данных (запросы, мутации). В Quorum не используется — данные идут через WebSocket. |
| **Next.js / Nuxt** | Фреймворки поверх React/Vue с SSR (Server-Side Rendering), статической генерацией и роутингом. Quorum — чистый CSR без SSR. |
| **SSE (Server-Sent Events)** | Односторонний стрим от сервера к клиенту по HTTP. В Quorum — fallback-канал к WebSocket (`APIService.streamTask`). |
| **WebSocket** | Двусторонний постоянный канал. В Quorum — основной транспорт (`ws://localhost:8000/ws`). |
| **CSR / SSR / SSG** | Client-Side Rendering (рендер в браузере), Server-Side Rendering (рендер на сервере), Static Site Generation (предгенерация статики). |

---

## Часть II. Фронтенд проекта Quorum (NoOversight)

### 2.1 Общий портрет

| Параметр | Значение |
|---|---|
| Тип приложения | SPA (Client-Side Rendering) |
| Ядро | React 18 + TypeScript 5.5 |
| Сборка | Vite 5 (esbuild в dev, Rollup в prod) |
| Состояние | Zustand 4 (7 slices, normalized state, persist) |
| Стили | Tailwind CSS 3 + кастомные CSS-классы (`index.css`) |
| Анимации | Framer Motion 11 |
| Markdown | react-markdown 10 + remark-gfm 4 |
| Реалтайм | WebSocket (основной канал) + SSE (fallback) |
| Логирование | Кастомный `Logger` (транспорты: Console + Remote, батчинг) |
| Экспорт | jsPDF (экспорт ответов в PDF) |
| Тесты | Отсутствуют (запланированы в `docs/05` — vitest) |

### 2.2 Структура проекта

```
frontend/
├── index.html            # Единственная HTML-страница: <div id="root"> + <script src="/src/main.tsx">
├── package.json          # npm-скрипты и зависимости
├── vite.config.ts        # Плагины, алиас '@', dev-прокси '/api' → :8000
├── tsconfig.json         # TypeScript (strict)
├── tailwind.config.js    # Тема Tailwind
├── postcss.config.js     # tailwindcss + autoprefixer
└── src/
    ├── main.tsx          # Точка входа: монтирование React + глобальные обработчики ошибок
    ├── App.tsx           # Корневой компонент: layout, WS-статус, отправка/остановка задач
    ├── index.css         # Tailwind-директивы + кастомные классы
    ├── components/       # Презентационные компоненты (15+)
    ├── hooks/            # useWebSocket, useLogger
    ├── services/         # API-клиенты, WebSocket, Logger (+ транспорты)
    ├── store/            # Zustand: типы, селекторы, 7 slices
    ├── types/            # Доменные TS-типы (события, агенты, сообщения)
    ├── utils/            # PDF-экспорт, время, парсинг tool-usage
    ├── shaders/          # GLSL-шейдеры для фоновой анимации
    └── vite-env.d.ts, shaders.d.ts
```

### 2.3 Жизненный цикл приложения

```
Браузер → GET / → index.html
  → main.tsx:
      - инициализация Logger (синглтон, sessionId)
      - глобальные слушатели: window 'error', 'unhandledrejection', visibilitychange
      - ReactDOM.createRoot(#root).render(<StrictMode><App/></StrictMode>)
  → App.tsx:
      - useWebSocket({ autoConnect: true }) → WebSocketService.connect() → ws://localhost:8000/ws
      - useEffect: loadSettings() из localStorage (zustand persist)
      - рендер: Header + ChatHistory + ChatWindow/ChatInput + AgentPanel (conditional)
      - ErrorBoundary оборачивает всё дерево
```

### 2.4 Слой состояния: Zustand + event sourcing

Хранилище — **единственный источник правды** (`single source of truth`). Все компоненты читают
состояние через хуки `useStore(selector)`, все изменения — только через actions слайсов.

```
useStore = create<RootStore>()(
  devtools(                     // Redux DevTools в dev-режиме
    persist(                    // localStorage под ключом 'quorum-store'
      (set, get, api) => ({
        ...createConversationSlice(set, get, api),  // conversationId, rounds, agent-диалоги
        ...createMessagesSlice(set, get, api),      // normalized: byId/allIds
        ...createAgentsSlice(set, get, api),        // normalized: byId/allIds
        ...createUISlice(set, get, api),            // isProcessing, error, showAgentPanel
        ...createStreamSlice(set, get, api),        // handleStreamEvent (event sourcing)
        ...createSettingsSlice(set, get, api),      // настройки + localStorage
        ...createHistorySlice(set, get, api),       // история диалогов, поиск, избранное
      })
    )
  )
)
```

**Ключевые решения:**

1. **Нормализованное состояние** — `messages: { byId: Record<id, Message>, allIds: string[] }`.
   O(1) доступ по id, денормализация через селекторы (`allIds.map(id => byId[id])`).

2. **Event sourcing через `streamSlice`.** ВСЕ WebSocket-события от бэкенда проходят через один
   метод `handleStreamEvent(event)`, внутри — `switch(event.type)` с 20+ кейсами
   (`init`, `agent_status`, `delegation`, `stream`, `complete`, `cancelled`,
   `agent_message_chunk`, `tool_use`, `tool_result` и др.). Это единая точка, где поток событий
   превращается в мутации слайсов. Такой подход легко отлаживать и тестировать.

3. **Двойная персистентность.**
   - `persist` (Zustand middleware) → `localStorage` (ключ `quorum-store`), `partialize()`
     исключает эфемерное состояние (UI/stream);
   - отдельно сообщения активного диалога сохраняются в `sessionStorage`
     (ключ `quorum-conversation-messages-{id}`) — для восстановления при перезагрузке вкладки.

4. **Селекторы — только для производных данных.** Действия читаются напрямую
   (`useStore((s) => s.addMessage)` — стабильная ссылка), чтобы не провоцировать лишние ре-рендеры.
   Это задокументировано в комментариях `selectors.ts` как дизайн-принцип.

### 2.5 Реалтайм-слой: WebSocket

**`WebSocketService`** (`services/websocket.ts`) — класс-синглтон (`getWebSocketService()`):

- `connect()` — установка соединения `ws://localhost:8000/ws`, promise с таймаутом 10s;
- **auto-reconnect** — до 10 попыток, интервал `3000ms × min(attempt, 3)`, сброс после успеха;
- **heartbeat** — `ping` каждые 30s (сервер отвечает `pong`);
- **ре-подписки после переподключения** — `resubscribe()` повторяет `subscribe` для всех сохранённых conversationId;
- шина обработчиков: `onMessage` / `onError` / `onConnectionChange` возвращают функции-отписки;
- протокол клиент→сервер: `ping`, `subscribe`, `unsubscribe`, `task`, `stop`.

**`useWebSocket`** (`hooks/useWebSocket.ts`) — React-обёртка: подключает обработчики в `useEffect`,
пробрасывает `isConnected`/`error` в локальный state, делегирует действия
(`sendTask`, `stopGeneration`, `subscribe`/`unsubscribe`).

**Ключевой поток данных «сообщение → LLM → ответ»:**

```
1. Пользователь печатает → ChatInput → App.handleSendMessage()
2. addMessage({role:'user'}) в стор (мгновенно появляется в ленте)
3. sendTask({ message, enableCollaboration: agentMode==='quorum', maxSubAgents: 3 })
   → WebSocketService.send({type:'task', task})
4. Backend: WS-route → ConversationService (сохранение в БД) → TaskOrchestrator.process_task()
5. Backend стримит события:
   init → agent_status → delegation → agent_thinking → agent_message_chunk
   → conversation_round_complete → stream (токены) → complete
6. Frontend: WS.onmessage → handleStreamEvent(event) → switch → мутации слайсов
7. Zustand-селекторы сигнализируют React → перерисовка ChatWindow/AgentPanel
```

Параллельно бэкенд сохраняет ответы в PostgreSQL (conversations/messages) — фронтенд это
не блокирует, а история доступна через REST `GET /conversations/{id}`.

### 2.6 Компонентный слой

| Компонент | Назначение | Особенности |
|---|---|---|
| `App` | Корневой layout, WS-статус, ошибки | Три панели: history / chat / agents |
| `ChatWindow` | Лента сообщений | Автоскролл с детекцией «пользователь прокрутил вверх», кнопка «вниз», индикатор Processing |
| `MessageBubble` | Одно сообщение | Markdown для assistant, экспорт в PDF, `memo` с логикой «всегда ре-рендерить последнее сообщение при стриминге» |
| `MarkdownRenderer` | Рендер markdown | react-markdown + remark-gfm, кастомные компоненты для code/inline-code/ссылок, `memo` по content |
| `ChatInput` | Поле ввода | Auto-resize textarea, Enter=send / Shift+Enter=новая строка, кнопка Stop |
| `AgentPanel` / `AgentCard` | Панель агентов | Active/Completed секции, анимации Framer Motion (AnimatePresence) |
| `AgentConversation` | «Разговор агентов» по раундам | Collapsible timeline: Round N, статус (Pending/Active/Complete), авто-сворачивание завершённых раундов |
| `AgentToolDisplay` / `ToolUsageDisplay` | Отображение результатов web search | Парсинг tool-usage из контента сообщений (`utils/toolParser.ts`) |
| `ChatHistory` | Левая панель истории | Список диалогов, поиск, избранное, загрузка диалога по REST |
| `Settings` / `QuorumSettings` | Модальные окна настроек | API-ключи, тема, режим solo/quorum, модели, раунды |
| `ModeSelector` | Переключатель solo/quorum | Управляет `agentMode` в настройках |
| `CostCalculator` / `TokenUsageDisplay` | Калькулятор стоимости токенов | UI поверх `/api/tokens/*` |
| `GLSLBackground` | Анимированный фон | WebGL/GLSL-шейдеры |
| `ErrorBoundary` | Защита от render-ошибок | Fallback UI вместо падения всего приложения |
| `Logo` | SVG-логотип | — |

**Паттерн презентации:** контейнер/презентация в одном файле. Компоненты не ходят напрямую
в сеть — сеть инкапсулирована в `services/` и `hooks/`, глобальное состояние — в `store/`.
Это соблюдает слоистость, аналогичную бэкенду (`api → core → infrastructure`).

### 2.7 Логирование

Кастомный `Logger` (`services/logger.ts`) — аналог structlog на бэкенде:

- **Транспорты**: `ConsoleTransport` (цветной вывод) и `RemoteTransport` (батчинг: batchSize=10,
  flushInterval=5s — отправка логов на remote endpoint).
- **Контекст-стек**: `createChild({component: 'X'})` → каждый логгер несёт контекст своего компонента;
  `useLogger`-хук добавляет автоматическое логирование mount/unmount.
- **Performance tracking**: `startPerformance('send-message')` / `endPerformance(...)` → длительность в логах.
- **Глобальная диагностика** в `main.tsx`: `window.onerror`, `unhandledrejection`, visibilitychange.

Каждое WS-событие логируется с эмодзи-маркером и метаданными — это де-факто дашборд
для отладки потока событий в консоли.

### 2.8 Обработка ошибок (frontend)

| Уровень | Механизм |
|---|---|
| Render | `ErrorBoundary` — fallback UI |
| WS | `useWebSocket` → `setError` → баннер в `App` |
| Store | `uiSlice.error` + `clearError()` |
| Stream | `case 'error'` в `handleStreamEvent` → setError + setProcessing(false) |
| Отмена | `case 'cancelled'` → статусы агентов → 'error', сообщение 'Cancelled' |
| API | `APIService` → throw Error с текстом ответа |
| Глобально | `window.onerror` / `unhandledrejection` → logger.error |

Защита от «опоздавших» событий: если стрим уже завершён (`isStreaming === false`), поздние
`agent_status`/`agent_message_chunk` игнорируются — это предотвращает откат завершённых агентов.

### 2.9 Стилизация

- **Tailwind CSS** (utility-first) в JSX-классах;
- кастомные CSS-классы (`header-clean`, `btn-minimal`, `message-user`, `agent-card-clean`,
  `history-panel-permanent`, `animate-slide-in-right`, `glow`, `gradient-border` и др.) — в `index.css`;
- **Framer Motion** для анимаций появления/исчезновения и layout-переходов;
- анимированный **WebGL/GLSL фон** (`GLSLBackground`, шейдеры в `src/shaders/`);
- тема: светлая/тёмная/system через настройки.

### 2.10 Сильные стороны фронтенда

1. **Чистая структура**: чёткое разделение `components / hooks / services / store / types / utils`.
2. **Нормализованное состояние + селекторы** — предсказуемый и производительный доступ к данным.
3. **Event sourcing через `handleStreamEvent`** — единая точка обработки всех 20+ типов событий.
4. **Грамотная работа с ре-рендерами**: `memo` на тяжёлых компонентах, стабильные ссылки actions,
   мемоизация markdown-рендера.
5. **Устойчивый WebSocket**: auto-reconnect с backoff, heartbeat, ре-подписки.
6. **Двойная персистентность** (localStorage для настроек/истории + sessionStorage для активного диалога).
7. **Кастомный Logger** с транспортами и производительностью — симметрия с бэкендовым structlog.

### 2.11 Слабые места и известные проблемы (из `docs/04`)

| Проблема | Анализ |
|---|---|
| **Нет тестов вообще** | Нет `test`-скрипта в `package.json`; высокий риск регрессий (план — vitest в `docs/05`) |
| **Батчинг WS-событий** | Каждый токен → `handleStreamEvent` → `set()` → потенциальный ре-рендер; при высокой частоте токенов возможны просадки |
| **localStorage-сериализация** | Zustand persist сериализует все сообщения при каждом изменении; длинные диалоги могут блокировать main thread |
| **Нет virtualized list** | `ChatWindow` рендерит все сообщения сразу; 1000+ сообщений → деградация |
| **PDF-экспорт (jsPDF)** | Синхронный рендер в main thread → возможен фриз UI на больших ответах |
| **RemoteTransport** | Нет queue/retry policy (flush каждые 5s) |
| **`tool_use`/`tool_result` — тупиковые** | Обработчики есть, но бэкенд не эмитит эти события (tool calling не реализован) |
| **API-ключ в localStorage** | Обифускация `btoa` — это НЕ шифрование; отмечено в коде как осознанное ограничение |
| **SSE fallback фактически не используется** | Основной канал — WS; `APIService.streamTask` существует, но вызывается редко |

### 2.12 Рекомендации (синхронизированы с `docs/05`)

Приоритет P1:
1. **Добавить тесты** (`vitest` + `@testing-library/react` + `jsdom`): первыми покрыть
   `streamSlice` (чистые функции event sourcing) и `selectors`.
2. **Виртуализировать список сообщений** (`@tanstack/react-virtual` или `react-window`) —
   самый заметный прирост на длинных диалогах.

Приоритет P2:
3. **Батчинг WS-событий** (requestAnimationFrame / микро-батч) для плавности стриминга.
4. **Вынести активный диалог из localStorage** в sessionStorage/IndexedDB (сообщения уже дублируются там).
5. **PDF-экспорт в Web Worker** или off-main-thread генерация.
6. **CI**: `npm ci → lint → tsc --noEmit → build → test` (предложено в `docs/05` §CI/CD).
7. **Sentry** (`@sentry/react`) для продакшн-ошибок.

### 2.13 Карта «файл → роль» (шпаргалка)

| Хотите понять… | Открыть |
|---|---|
| Запуск и монтирование | `index.html`, `src/main.tsx`, `vite.config.ts` |
| Layout и события | `src/App.tsx` |
| WebSocket-клиент | `src/services/websocket.ts`, `src/hooks/useWebSocket.ts` |
| Обработку событий бэкенда | `src/store/slices/streamSlice.ts` |
| Состояние сообщений/агентов | `src/store/slices/messagesSlice.ts`, `agentsSlice.ts` |
| Настройки и персистентность | `src/store/slices/settingsSlice.ts`, `store/index.ts` (partialize) |
| Типы протокола | `src/types/index.ts` (StreamEvent, TaskRequest, Message…) |
| Селекторы | `src/store/selectors.ts` |
| Логирование | `src/services/logger.ts`, `hooks/useLogger.ts` |
| Рендер ответов | `src/components/MarkdownRenderer.tsx`, `MessageBubble.tsx` |
| Панель агентов | `src/components/AgentPanel.tsx`, `AgentCard.tsx`, `AgentConversation.tsx` |
| REST/SSE fallback | `src/services/api.ts`, `settingsApi.ts`, `tokenApi.ts` |

---

## Глоссарий (мини)

| Термин | Определение |
|---|---|
| **SPA** | Одностраничное приложение: один HTML, интерфейс строит JS |
| **MPA** | Многостраничное приложение: каждая страница — отдельный HTML с сервера |
| **CSR** | Рендер интерфейса в браузере (как в Quorum) |
| **SSR** | Рендер HTML на сервере (Next.js, или Jinja2 в MPA) |
| **Virtual DOM** | Дерево элементов в памяти, diff которого React патчит в настоящий DOM |
| **Reconciliation** | Сравнение старого и нового деревьев React |
| **JSX** | Разметка в JS/TS, компилируемая в вызовы React.createElement |
| **Hook** | Функция-«хук» в React (useState, useEffect…) для state и эффектов |
| **HMR** | Hot Module Replacement: обновление модуля без перезагрузки страницы |
| **Bundler** | Программа сборки всех модулей в бандлы (Rollup в Vite) |
| **Tree-shaking** | Вырезание неиспользуемого кода при сборке |
| **Сборщик / build tool** | Vite, Webpack, Parcel — инструменты dev-сервера и сборки |
| **Шаблонизатор** | Инструмент генерации HTML из данных на сервере (Jinja2, Jinja, Django Templates) |
| **Utility-first CSS** | Стилизация утилитами (Tailwind) вместо семантических классов |
| **Event sourcing** | Паттерн: изменения состояния — только через обработку событий |
| **Normalized state** | Хранение сущностей в `byId`/`allIds` для O(1)-доступа |

---

*Отчёт дополняет `docs/01`–`docs/05` и не претендует на замену файлов `04`/`05` — это обучающий
и обзорный материал по фронтенду проекта.*
