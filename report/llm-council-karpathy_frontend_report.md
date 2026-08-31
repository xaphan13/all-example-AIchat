# Отчет по фронтенду: LLM Council Karpathy

Проект `llm-council-karpathy` имеет более простой и легковесный фронтенд. Он ориентирован на чат-интерфейс, разбитый на стадии.

## Технологии и библиотеки

*   **React (v19.2.0)**: Последняя версия React для построения UI. В отличие от Quorum, здесь используется стандартный JavaScript (JSX), а не TypeScript.
*   **Vite**: Инструмент сборки для быстрой разработки.
*   **React Markdown**: Для отображения отформатированного текста (Markdown), который возвращают языковые модели.
*   **CSS**: Используется стандартный CSS (в файлах вроде `App.css`, `ChatInterface.css`), без утилитных фреймворков типа Tailwind.

## Архитектура и структура

Структура в папке `src/` предельно проста:
*   **`api.js`**: Изолированная логика для работы с REST API сервера (fetch/axios).
*   **`components/`**: Содержит компоненты интерфейса (Sidebar, ChatInterface, Stage1, Stage2, Stage3). Каждый компонент обычно имеет свой одноименный `.css` файл.
*   **`App.jsx`**: Корневой компонент, управляющий основным состоянием приложения.

## Как связаны между собой элементы (Учебное пособие)

В этом проекте для управления состоянием используются стандартные React-хуки (`useState`, `useEffect`), а не сторонние библиотеки, что делает его отличным примером базовой архитектуры React.

**Корневое состояние в `App.jsx`**:
Вся информация о беседах хранится в `App.jsx` и передается дочерним компонентам через пропсы.

```jsx
// App.jsx
import { useState, useEffect } from 'react';
import Sidebar from './components/Sidebar';
import ChatInterface from './components/ChatInterface';
import { api } from './api';

function App() {
  const [conversations, setConversations] = useState([]);
  const [currentConversationId, setCurrentConversationId] = useState(null);

  useEffect(() => {
    // Загрузка бесед при старте
    api.listConversations().then(setConversations);
  }, []);

  return (
    <div className="app">
      <Sidebar
        conversations={conversations}
        onSelect={setCurrentConversationId}
      />
      <ChatInterface
        conversationId={currentConversationId}
        // ...
      />
    </div>
  );
}
```
*Почему так написано?* Это паттерн "Поднятие состояния" (Lifting State Up). Поскольку и `Sidebar` (список бесед), и `ChatInterface` (текущая беседа) зависят от информации о беседах, состояние хранится в их ближайшем общем предке (`App`), что позволяет компонентам синхронизироваться.

**Инкапсуляция API логики**:
Все запросы к бэкенду вынесены в `api.js`.

```javascript
// api.js
export const api = {
  listConversations: async () => {
    const response = await fetch('/api/conversations');
    return response.json();
  }
};
```
*Почему так написано?* Это разделяет бизнес-логику и UI. Компоненты ничего не знают о URL-адресах, заголовках или формате ответов. Если API изменится, нужно будет обновить только один файл `api.js`.

**Рендеринг стадий**:
Интерфейс чата разбит на компоненты стадий (`Stage1`, `Stage2`, `Stage3`). В `ChatInterface.jsx` эти стадии рендерятся условно или последовательно.
Markdown рендерится с помощью `react-markdown`:

```jsx
// Пример использования ReactMarkdown в компонентах
import ReactMarkdown from 'react-markdown';

function Message({ content }) {
  return (
    <div className="message-content">
      <ReactMarkdown>{content}</ReactMarkdown>
    </div>
  );
}
```
*Почему так написано?* Языковые модели возвращают текст в формате Markdown (с жирным текстом, списками, блоками кода). `react-markdown` безопасно парсит эту строку и превращает её в валидные React-компоненты.