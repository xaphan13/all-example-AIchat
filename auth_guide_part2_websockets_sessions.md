# Руководство по аутентификации и авторизации в современных веб-приложениях (Часть 2: Анонимные сессии и WebSockets)

В предыдущей части мы рассмотрели классическую аутентификацию по логину и паролю. Однако, не всем приложениям требуется, чтобы пользователь обязательно создавал аккаунт для начала работы. Многие современные чат-боты позволяют использовать сервис "на лету", сохраняя историю диалога в рамках сессии.

В этой статье мы рассмотрим, как реализована поддержка анонимных сессий и работа с WebSockets в проектах **GroqStreamChain** и **Quorum**.

---

## 1. Анонимные сессии в GroqStreamChain

Проект **GroqStreamChain** представляет собой чат на базе LLM. В нем нет базы данных пользователей, логинов и паролей. Вместо этого приложение идентифицирует пользователя по `session_id`, который генерируется сервером и сохраняется на стороне клиента в `localStorage`.

### Генерация сессии при подключении

Когда клиент устанавливает соединение по WebSocket, сервер (в `GroqStreamChain/server.py`) автоматически генерирует уникальный `session_id` с использованием библиотеки `uuid`.

```python
import uuid

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket) -> str:
        await websocket.accept()
        # Генерация уникального ID сессии
        session_id = str(uuid.uuid4())
        self.active_connections[session_id] = websocket

        # Сохранение сессии в in-memory хранилище
        chat_sessions[session_id] = ChatSession(id=session_id)
        return session_id
```

Сразу после подключения сервер отправляет клиенту этот `session_id`:

```python
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    session_id = await manager.connect(websocket)
    # Отправка session_id клиенту
    await websocket.send_json({"type": "session_id", "session_id": session_id})
```

### Сохранение на клиенте

На стороне клиента (в `GroqStreamChain/static/js/main.js`) браузер получает этот `session_id` и сохраняет его в `localStorage`. Это позволяет в будущем, при необходимости (например, при обрыве связи), отправить этот ID обратно на сервер и восстановить контекст чата.

```javascript
ws.onmessage = function(event) {
    const data = JSON.parse(event.data);
    switch(data.type) {
        case 'session_id':
            console.log('Received session ID:', data.session_id);
            sessionId = data.session_id;
            // Сохраняем сессию в локальное хранилище браузера
            localStorage.setItem('chatSessionId', sessionId);
            break;
        // ... обработка других сообщений
    }
};
```

Такой подход максимально упрощает порог входа для пользователя, но имеет недостаток — история сообщений привязана к конкретному браузеру (и очистится, если почистить кэш).

---

## 2. Управление соединениями WebSockets в Quorum

Проект **Quorum** имеет более сложную и масштабируемую архитектуру. Работа с веб-сокетами вынесена в отдельную инфраструктурную директорию `Quorum/backend/src/infrastructure/websocket/manager.py`.

### Разделение connection_id и session_id

Важное отличие от предыдущего примера — это четкое разделение `connection_id` (идентификатора самого физического соединения) и `session_id` (логической сессии, связанной с задачей или пользователем).

```python
class WebSocketManager:
    def __init__(self):
        # Хранение активных подключений: {connection_id: websocket}
        self.active_connections: Dict[str, WebSocket] = {}
        # Связь соединения с сессией: {connection_id: session_id}
        self.connection_sessions: Dict[str, str] = {}

    async def connect(self, websocket: WebSocket) -> str:
        await websocket.accept()
        connection_id = uuid.uuid4().hex
        self.active_connections[connection_id] = websocket

        # Создание логической сессии
        session_id = f"session_{uuid.uuid4().hex[:12]}"
        self.connection_sessions[connection_id] = session_id

        # Отправка идентификаторов клиенту
        await self.send_personal_message(
            {"type": "connection_established", "connection_id": connection_id, "session_id": session_id},
            connection_id
        )
        return connection_id
```

Это разделение позволяет, например, одному пользователю (одной сессии) иметь несколько открытых вкладок браузера (несколько `connection_id`), хотя в данном базовом классе на каждое соединение создается своя сессия. В более сложных системах вы могли бы принимать `session_id` от клиента при аутентификации WebSocket соединения и привязывать новый `connection_id` к уже существующей сессии.

### Очистка ресурсов

При отключении клиента (отключение интернета, закрытие вкладки) менеджер соединений должен корректно подчищать за собой, удаляя как `connection_id`, так и связку с `session_id`.

```python
    def disconnect(self, connection_id: str):
        """Отключение клиента и очистка сессии."""
        if connection_id in self.active_connections:
            del self.active_connections[connection_id]

        if connection_id in self.connection_sessions:
            del self.connection_sessions[connection_id]
```

## Вывод по Части 2

Анонимные сессии — отличный выбор для приложений, где важна скорость начала работы (например, чат-боты или поисковые интерфейсы). Использование `localStorage` и передачи `session_id` через WebSockets позволяет сохранять контекст диалога без необходимости заставлять пользователя вводить email и пароль.

В [следующей части](auth_guide_part3_external_apis.md) мы разберем нестандартные подходы к авторизации: проксирование запросов к внешним сервисам, управление чужими API-ключами и работу с протоколом MCP.
