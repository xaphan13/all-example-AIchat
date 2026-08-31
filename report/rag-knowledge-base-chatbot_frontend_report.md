# Отчет по фронтенду: RAG Knowledge Base Chatbot

Проект `rag-knowledge-base-chatbot` — это полноценное Single Page Application (SPA) с авторизацией, роутингом и дашбордом.

## Технологии и библиотеки

*   **React (v19.2.4)**: Основа интерфейса.
*   **Vite**: Инструмент сборки.
*   **TypeScript**: Для строгой типизации пропсов, состояний и ответов API.
*   **Tailwind CSS (v4)**: Используется для стилизации. Версия 4 настраивается через `@tailwindcss/vite`.
*   **React Router DOM (v7)**: Библиотека для управления навигацией (маршрутизацией) между различными страницами (Дашборд, Настройки, Чат и т.д.) без перезагрузки страницы.
*   **Axios**: Мощный HTTP-клиент для работы с API, использующий интерсепторы для управления токенами.
*   **Lucide React**: Библиотека иконок.

## Архитектура и структура

Проект в `src/` хорошо структурирован для крупного приложения:
*   **`pages/`**: Компоненты-страницы, каждая из которых соответствует определенному маршруту (URL) (например, `Dashboard.tsx`, `Login.tsx`).
*   **`contexts/`**: React Context для управления глобальными состояниями (например, `AuthContext.tsx`).
*   **`api/`**: Конфигурация Axios (`client.ts`).
*   **`App.tsx`**: Настройка роутера и основного макета с боковой панелью.

## Как связаны между собой элементы (Учебное пособие)

**Аутентификация через Context API**:
В приложении есть страницы, доступные только авторизованным пользователям. Для этого используется `AuthContext`.

```tsx
// contexts/AuthContext.tsx
import { createContext, useContext, useState } from 'react';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [token, setToken] = useState(localStorage.getItem('support_ai_token'));

  // Логика логина, логаута, проверки токена...

  return (
    <AuthContext.Provider value={{ user, token, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
```
*Почему так написано?* Context API позволяет сделать данные (текущий пользователь, токен) доступными любому компоненту в дереве без необходимости передавать их через пропсы на каждом уровне. `AuthProvider` оборачивает всё приложение в `main.tsx`.

**Защищенные маршруты (Routing)**:
В `App.tsx` используется `react-router-dom` для навигации. Доступ к страницам зависит от состояния авторизации из контекста.

```tsx
// App.tsx
import { Routes, Route, Navigate } from 'react-router-dom';
import { useAuth } from './contexts/AuthContext';
import Dashboard from './pages/Dashboard';
import Login from './pages/Login';

function App() {
  const { user } = useAuth();

  return (
    <Routes>
      {/* Публичный маршрут */}
      <Route path="/login" element={<Login />} />

      {/* Защищенный маршрут */}
      <Route
        path="/dashboard"
        element={user ? <Dashboard /> : <Navigate to="/login" replace />}
      />
    </Routes>
  );
}
```
*Почему так написано?* Если пользователь не авторизован (`user` равно null), компонент `<Navigate>` немедленно перенаправляет его на страницу логина. Это безопасный способ защитить клиентские маршруты.

**Настройка Axios Интерсепторов**:
В файле `api/client.ts` настроен экземпляр Axios, который автоматически добавляет токен ко всем запросам.

```typescript
// api/client.ts
import axios from 'axios';

const http = axios.create({ baseURL: '/v1' });

// Interceptor для добавления токена
http.interceptors.request.use((config) => {
  const token = localStorage.getItem('support_ai_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export const api = http;
```
*Почему так написано?* Вместо того чтобы вручную читать токен из `localStorage` и добавлять его в каждый вызов `fetch` или `axios.get`, интерсептор делает это централизованно, перед тем как запрос уйдет на сервер. Это устраняет дублирование кода и снижает вероятность ошибки.