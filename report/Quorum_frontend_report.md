# Отчет по фронтенду: Quorum

Проект `Quorum` представляет собой сложный пользовательский интерфейс для системы, управляемой агентами. Он построен с использованием современных технологий и строгой типизации.

## Технологии и библиотеки

*   **React (v18.3.1)**: Основная библиотека для построения пользовательского интерфейса.
*   **Vite**: Инструмент сборки, обеспечивающий быструю разработку и оптимизированную сборку для продакшена.
*   **TypeScript**: Используется для строгой типизации, что уменьшает количество ошибок и улучшает автодополнение в редакторах.
*   **Tailwind CSS**: Утилитный CSS-фреймворк для стилизации компонентов без необходимости писать отдельный CSS (хотя в проекте также используются кастомные стили и шейдеры).
*   **Zustand (v4.5.5)**: Легковесная библиотека для управления состоянием приложения.
*   **Framer Motion**: Библиотека для создания плавных анимаций (например, при появлении агентов или сообщений).
*   **React Markdown & Remark GFM**: Для рендеринга ответов агентов, содержащих форматирование Markdown и таблицы.
*   **Lucide React**: Коллекция иконок, используемых в интерфейсе.

## Архитектура и структура

Проект структурирован в папке `src/` следующим образом:

1.  **components/**: Содержит переиспользуемые React-компоненты (например, `ChatWindow`, `AgentCard`, `AgentPanel`).
2.  **store/**: Логика управления глобальным состоянием с помощью Zustand.
3.  **services/**: Логика взаимодействия с API (`api.ts`), WebSockets (`websocket.ts`) и логирования.
4.  **hooks/**: Кастомные хуки, такие как `useWebSocket` и `useLogger`.
5.  **shaders/**: GLSL файлы для создания кастомных анимированных фонов (например, `background.frag.glsl`).

## Как связаны между собой элементы (Учебное пособие)

Центральным звеном приложения является **Управление состоянием (Store)**. В `Quorum` используется `Zustand`. Состояние разделено на "слайсы" (slices), чтобы код был модульным.

Например, состояние пользовательского интерфейса (UI) хранится в отдельном слайсе `uiSlice.ts`:

```typescript
// store/slices/uiSlice.ts
import { StateCreator } from 'zustand';

export const createUISlice: StateCreator<RootStore, [], [], UISlice> = (set, get) => ({
  showAgentPanel: true,
  isProcessing: false,
  error: null,
  inputValue: '',

  setShowAgentPanel: (show: boolean) => set({ showAgentPanel: show }),
  setProcessing: (processing: boolean) => set({ isProcessing: processing }),
  // ... другие действия
});
```
*Почему так написано?* Использование Zustand позволяет избежать "prop drilling" (передачи пропсов через множество промежуточных компонентов). Разделение на слайсы (`createUISlice`, `createMessagesSlice` и др.) и объединение их в `RootStore` в `store/index.ts` сохраняет чистоту и масштабируемость кода.

В корневом компоненте **`App.tsx`** мы подписываемся на это состояние с помощью селекторов:

```tsx
// App.tsx
import { useStore } from '@/store';
import { selectMessages, selectAgents } from '@/store/selectors';

function App() {
  // Получаем состояния через селекторы для оптимизации ререндеров
  const messages = useStore(selectMessages);
  const showAgentPanel = useStore((state) => state.showAgentPanel);
  const setShowAgentPanel = useStore((state) => state.setShowAgentPanel);

  return (
    <div>
       {/* Компоненты используют это состояние */}
       <ChatWindow messages={messages} />
       {showAgentPanel && <AgentPanel />}
    </div>
  );
}
```

**Анимации с Framer Motion**:
Когда агент начинает думать или отвечать, мы хотим показать это красиво. В `AgentCard.tsx` используется `motion.div`:

```tsx
// components/AgentCard.tsx
import { motion } from 'framer-motion';

export const AgentCard = ({ agent }) => {
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.95, y: 10 }}
      animate={{ opacity: 1, scale: 1, y: 0 }}
      exit={{ opacity: 0, scale: 0.95, y: -10 }}
      transition={{ duration: 0.25 }}
    >
      <h3>{agent.agentType}</h3>
      <p>{agent.status}</p>
    </motion.div>
  );
};
```
*Почему так написано?* `framer-motion` предоставляет декларативный API для создания сложных анимаций. Свойства `initial`, `animate` и `exit` автоматически обрабатывают появление и исчезновение элемента из DOM, делая интерфейс отзывчивым и "живым".

**Взаимодействие с Backend**:
Для связи с сервером используется кастомный хук `useWebSocket`, который инкапсулирует логику установки соединения, обработки сообщений и переподключения, обновляя Zustand store при получении новых данных.
