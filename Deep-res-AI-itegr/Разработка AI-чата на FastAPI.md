# **Архитектура и реализация веб\-чата для доступа к моделям искусственного интеллекта на базе FastAPI**

## **Эволюция парадигмы взаимодействия с большими языковыми моделями**

Интеграция больших языковых моделей (LLM), таких как OpenAI GPT-4, Anthropic Claude или локальных решений на базе Ollama, требует фундаментального пересмотра традиционных архитектурных подходов к проектированию веб\-сервисов. В классической модели синхронного HTTP-взаимодействия клиент отправляет запрос и ожидает полного формирования ответа сервером1. В контексте генеративного искусственного интеллекта этот подход становится критическим узким местом. Процесс авторегрессионной генерации, при котором модель предсказывает каждый последующий токен на основе предыдущих, может занимать десятки секунд в зависимости от размера контекста и вычислительных мощностей2. В результате задержка до появления первого токена (Time-To-First-Token, TTFT) превышает допустимые нормы пользовательского опыта, оставляя клиента в состоянии неопределенности4.

Решением этой проблемы является внедрение архитектуры потоковой передачи данных (streaming), позволяющей отправлять сгенерированные токены клиенту в режиме реального времени по мере их появления1. Для реализации подобных высоконагруженных систем с интенсивным вводом-выводом (I/O-bound) в экосистеме Python де\-факто стандартом стал фреймворк FastAPI. Базируясь на спецификации ASGI (Asynchronous Server Gateway Interface) через библиотеку Starlette и используя библиотеку asyncio для неблокирующего выполнения задач, FastAPI обеспечивает экстремально высокую пропускную способность, сопоставимую с решениями на Node.js и Go1. Строгая типизация на основе Pydantic, автоматическая генерация документации OpenAPI и нативная поддержка асинхронных генераторов делают FastAPI оптимальным выбором для разработки масштабируемых платформ AI-чатов1.

## **Анализ транспортных протоколов для потоковой передачи данных**

Проектирование инфраструктуры чата требует обоснованного выбора механизма доставки данных от сервера к клиенту. Инженеры традиционно рассматривают три основных паттерна: поллинг (HTTP Polling), Server-Sent Events (SSE) и WebSockets. Ошибочно полагать, что WebSockets являются безусловно лучшим решением для любых задач реального времени; выбор должен диктоваться направленностью потоков данных и требованиями к управлению состоянием8.

Поллинг предполагает периодическую отправку клиентом HTTP-запросов для проверки наличия новых токенов. Хотя этот метод прост в реализации и обходит любые ограничения прокси-серверов, он создает колоссальную избыточную нагрузку на сервер (CPU и сетевой стек) из\-за накладных расходов на установку TCP-соединений и передачу HTTP-заголовков в ситуациях, когда новые данные отсутствуют8. Для потоковой передачи LLM с высокой частотой генерации токенов поллинг считается антипаттерном12.

Протоколы Server-Sent Events (SSE) и WebSockets представляют собой более эффективные решения, однако они решают принципиально разные архитектурные задачи. SSE функционирует поверх стандартного протокола HTTP, оставляя соединение открытым и позволяя серверу однонаправленно «проталкивать» текстовые события клиенту1. WebSockets, напротив, инициируются через HTTP-запрос (Upgrade), после чего переходят на чистый TCP-канал, обеспечивая полнодуплексную двунаправленную связь с передачей как текстовых, так и бинарных фреймов12.

| Характеристика | Server-Sent Events (SSE) | WebSockets |
| :---- | :---- | :---- |
| **Направление потока** | Сервер \-\> Клиент (однонаправленное) | Клиент \<-\> Сервер (двунаправленное) |
| **Сетевой уровень** | Стандартный HTTP/1.1 или HTTP/2 | TCP (после HTTP Upgrade) |
| **Формат сообщений** | Исключительно текстовый (UTF-8) | Текстовые и бинарные фреймы |
| **Управление соединением** | Автоматическое переподключение (браузер) | Требует ручной реализации логики |
| **Проксирование и балансировка** | Нативная поддержка HTTP-инфраструктурой | Требует настройки (Sticky sessions и др.) |
| **Потребление памяти (100k клиентов)** | Сниженное (\~3.1 ГБ в тестах Rust/Axum) | Повышенное (\~5.2 ГБ в тестах Rust/Axum) |

Данные бенчмарков, проведенных при тестировании 100 000 одновременных подключений, демонстрируют, что SSE потребляет примерно на 40% меньше оперативной памяти на стороне сервера по сравнению с WebSockets14. Разница обусловлена механикой протоколов: WebSocket требует поддержания выделенной задачи (Task) для каждого соединения, управления буферами двунаправленных фреймов, парсинга заголовков с маскированием и поддержания таймеров heartbeat (ping/pong)14. При этом разница в задержке (latency) между SSE и WebSockets составляет всего около 3 миллисекунд, что абсолютно незаметно при потоковой передаче текста16. Таким образом, для классического AI-чата, где пользователь отправляет длинный запрос и ожидает непрерывный поток токенов от модели, протокол SSE является наиболее эффективным и легковесным решением17. WebSockets становятся необходимыми только тогда, когда архитектура переходит к агентам второго поколения (Agentic Workflows), требующим мгновенного вмешательства пользователя в процесс работы AI (human-in-the-loop) или двунаправленной передачи голоса12.

## **Интеграция Server-Sent Events (SSE) в FastAPI**

Реализация SSE в FastAPI базируется на использовании асинхронных генераторов и класса StreamingResponse. Протокол SSE требует специфического форматирования отправляемых данных. Каждое сообщение должно начинаться с префикса data:, содержать полезную нагрузку и завершаться двумя символами переноса строки (\\n\\n), что сигнализирует браузерному API EventSource о завершении события1.

### **Потоковая передача данных от OpenAI**

Взаимодействие с моделями OpenAI осуществляется через официальную библиотеку, предоставляющую асинхронный клиент AsyncOpenAI. Использование флага stream=True заставляет библиотеку возвращать асинхронный итератор, который выдает чанки данных по мере их генерации на серверах OpenAI1.

Архитектурно правильная реализация в FastAPI требует создания изолированного генератора, который оборачивает вызов к API и форматирует результаты. Клиент инициализируется глобально для переиспользования соединений. В процессе итерации по потоку необходимо отлавливать события типа response.output\_text.delta (или аналогичные, в зависимости от версии API и модели), извлекать строковые токены и передавать их через оператор yield1. По завершении генерации отправляется специальный маркер \[DONE\], позволяющий клиентскому приложению корректно закрыть соединение и обновить состояние пользовательского интерфейса1.

&nbsp;

&nbsp;

&nbsp;

Python

import os  
import asyncio  
import logging  
from typing import AsyncGenerator  
from fastapi import FastAPI, Request  
from fastapi.responses import StreamingResponse  
from pydantic import BaseModel  
from openai import AsyncOpenAI

app \= FastAPI()  
\# Инициализация клиента вне контекста запроса для переиспользования соединений  
openai\_client \= AsyncOpenAI(api\_key=os.environ.get("OPENAI\_API\_KEY"))  
logger \= logging.getLogger(\_\_name\_\_)

class ChatMessage(BaseModel):  
&nbsp;&nbsp;&nbsp;&nbsp;content: str

async def generate\_openai\_stream(prompt: str, request: Request) \-\> AsyncGenerator\[str, None\]:  
&nbsp;&nbsp;&nbsp;&nbsp;try:  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;stream \= await openai\_client.chat.completions.create(  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;model="gpt-4o-mini",  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;messages=\[{"role": "user", "content": prompt}\],  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;stream=True,  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;stream\_options={"include\_usage": True}  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;)  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;\# Отправка стартового события для инициализации UI  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;yield "event: start\\ndata: \[START\]\\n\\n"  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;async for chunk in stream:  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;\# Проверка отключения клиента для предотвращения холостой работы LLM  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;if await request.is\_disconnected():  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;logger.info("Клиент разорвал соединение. Прерывание генерации.")  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;break  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;if chunk.choices and chunk.choices\[0\].delta.content:  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;text\_chunk \= chunk.choices\[0\].delta.content  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;\# Экранирование переносов строк внутри JSON-строк для надежности  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;safe\_text \= text\_chunk.replace('\\n', '\\\\n')  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;yield f"data: {safe\_text}\\n\\n"  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;yield "event: end\\ndata: \[DONE\]\\n\\n"  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;  
&nbsp;&nbsp;&nbsp;&nbsp;except asyncio.CancelledError:  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;logger.warning("Генерация прервана на уровне ASGI-сервера.")  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;raise  
&nbsp;&nbsp;&nbsp;&nbsp;except Exception as e:  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;logger.error(f"Ошибка интеграции с OpenAI: {e}")  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;yield f"event: error\\ndata: {str(e)}\\n\\n"

@app.post("/api/chat/openai")  
async def chat\_endpoint(message: ChatMessage, request: Request):  
&nbsp;&nbsp;&nbsp;&nbsp;return StreamingResponse(  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;generate\_openai\_stream(message.content, request),  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;media\_type="text/event-stream",  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;headers={  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"Cache-Control": "no-cache",  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"Connection": "keep-alive",  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"X-Accel-Buffering": "no"  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;}  
&nbsp;&nbsp;&nbsp;&nbsp;)

### **Специфика работы с Anthropic и локальными моделями**

Различные провайдеры AI-моделей имеют свои особенности работы с асинхронными потоками. Библиотека Anthropic (модели семейства Claude) требует использования асинхронных менеджеров контекста (async with) при работе с потоком. Контекстный менеджер гарантирует, что HTTP-соединение с серверами Anthropic будет корректно закрыто даже в случае возникновения сетевой ошибки или отмены задачи на сервере FastAPI5. Внутри контекста stream.text\_stream предоставляет итератор, отдающий чистые текстовые токены, что упрощает парсинг по сравнению со сложной структурой JSON-ответов OpenAI5.

Для развертывания полностью автономных чатов часто используются локальные модели через сервер Ollama. В этом случае взаимодействие строится не на специализированных SDK, а на использовании сырого HTTP-клиента httpx.AsyncClient. Архитектурный паттерн требует передачи флага stream=True (или эквивалентного параметра в JSON-теле) и использования метода client.stream(). Внутри асинхронного контекстного менеджера ответ читается по частям с помощью response.aiter\_lines(), декодируется из JSON, и полученные токены отправляются клиенту в формате SSE21. Важным аспектом работы с httpx является настройка параметров тайм-аута, так как загрузка локальной модели в VRAM при первом запросе может занимать продолжительное время, превышающее стандартные 5 секунд23.

## **Преодоление инфраструктурных барьеров потоковой передачи**

Развертывание потоковых SSE-эндпоинтов в производственной среде сопряжено с рядом неочевидных проблем, способных полностью разрушить функциональность реального времени. На локальном сервере токены могут отображаться плавно, однако в Production-среде клиенты часто получают ответ целиком с большой задержкой24.

### **Нейтрализация буферизации обратных прокси-серверов**

Ключевой причиной задержек является поведение обратных прокси-серверов и балансировщиков нагрузки. Программное обеспечение, такое как Nginx или HAProxy, по умолчанию стремится оптимизировать сетевой трафик путем буферизации ответов бэкенда. Прокси-сервер накапливает данные до тех пор, пока буфер не заполнится или соединение не будет закрыто, после чего отправляет весь массив данных клиенту одним TCP-пакетом17. В контексте AI-чата это приводит к тому, что пользователь не видит генерацию токенов, а получает готовый ответ через длительное время24.

Для отключения этого механизма FastAPI-приложение должно отдавать специализированные HTTP-заголовки. Наиболее важным из них является X-Accel-Buffering: no, который сообщает Nginx о необходимости немедленной сквозной передачи данных клиенту по мере их поступления от ASGI-сервера17. Дополнительно необходимо устанавливать Cache-Control: no-cache для предотвращения кеширования ответов на уровне CDN и промежуточных узлов1.

### **Проблема обрыва соединений и утечки ресурсов**

Веб-приложения подвержены частым непредсказуемым разрывам соединений: пользователь может закрыть вкладку, переключиться на другую сеть на мобильном устройстве или потерять сигнал. В стандартной синхронной модели программирования разрыв соединения обрабатывается сервером после завершения вычислений. Однако в асинхронных генераторах, если клиент отключается, генератор может продолжить работу в фоновом режиме, запрашивая новые токены у платного API и расходуя вычислительные ресурсы26.

Для решения этой проблемы необходимо на каждой итерации цикла async for проверять статус соединения с помощью метода await request.is\_disconnected()26. Однако этот подход не спасает, если зависает сам внешний API (например, OpenAI перестает присылать чанки). В этом случае корутина блокируется на ожидании новых данных и никогда не доходит до проверки статуса. Надежным архитектурным паттерном является использование асинхронных менеджеров контекста (через модуль contextlib или anyio.create\_task\_group), которые запускают фоновую задачу мониторинга сигнала http.disconnect. При получении сигнала эта задача принудительно отменяет текущую корутину генерации, предотвращая утечки ресурсов27.

### **Защита транзакций баз данных при отменах задач**

После завершения потоковой передачи токенов возникает бизнес-необходимость сохранить диалог в базу данных (PostgreSQL, MongoDB) и зафиксировать количество потраченных токенов (биллинг)26. Разработчики часто совершают фатальную ошибку, помещая код записи в БД в блок finally внутри генератора, используя ту же сессию базы данных, что была открыта при инициализации запроса.

Если клиент отключается до завершения генерации, ASGI-сервер (например, Uvicorn) инициирует отмену задачи (asyncio.CancelledError). Исключение распространяется по стеку вызовов, прерывая все операции. Если отмена происходит между операциями session.flush() и session.commit(), транзакция остается незавершенной. Соединение в пуле (Connection Pool) переходит в состояние "idle in transaction", удерживая эксклюзивные блокировки на строках в базе данных. Под высокой нагрузкой это приводит к стремительному исчерпанию пула соединений и полному отказу сервиса26.

Правильное решение базируется на двух принципах. Во-первых, для пост-обработки должна открываться совершенно новая, независимая сессия базы данных. Во-вторых, выполнение логики сохранения должно быть обернуто в функцию asyncio.shield(). Эта функция создает защитный барьер: если внешняя задача отменяется из\-за отключения клиента, внутренний корутинный блок, переданный в shield, продолжает свое выполнение в цикле событий до корректного завершения транзакции26.

## **Проектирование двунаправленных систем на базе WebSockets**

Несмотря на доминирование SSE для передачи сгенерированного текста, интеграция сложных мультимодальных моделей или систем на базе AI-агентов (Autonomous Agents) требует перехода на протокол WebSockets. Когда модель анализирует запрос и решает вызвать внешнюю функцию (Tool Calling), например, выполнить системную команду или обратиться к корпоративной базе данных, она может потребовать явного подтверждения от пользователя18. Поскольку SSE является однонаправленным протоколом, отправка подтверждения потребует инициализации нового POST-запроса, что усложняет координацию состояний. WebSocket решает эту проблему, обеспечивая единый полнодуплексный канал для потока токенов, запросов на использование инструментов и пользовательских ответов12.

### **Инкапсуляция состояний через Connection Manager**

В отличие от stateless-природы HTTP/REST, WebSocket-соединения хранят состояние на уровне сервера31. FastAPI требует явного управления жизненным циклом каждого сокета. Эта ответственность возлагается на паттерн ConnectionManager, который инкапсулирует логику принятия подключений, их хранения, отправки направленных сообщений и широковещательной рассылки (broadcasting)33.

Жизненный цикл WebSocket-эндпоинта в FastAPI состоит из трех фаз: ожидание подключения, бесконечный цикл приема-передачи сообщений и обработка отключения. Вызов await websocket.accept() завершает процедуру рукопожатия (handshake) и устанавливает TCP-соединение31. Важнейшим аспектом реализации является обработка исключения WebSocketDisconnect. Если клиент закрывает браузер, разорванное соединение вызывает данное исключение на сервере. Отсутствие блока try/except для перехвата WebSocketDisconnect приведет к неконтролируемому падению всего корутинного обработчика31.

&nbsp;

&nbsp;

&nbsp;

Python

from fastapi import FastAPI, WebSocket, WebSocketDisconnect  
from typing import Dict  
import logging

logger \= logging.getLogger(\_\_name\_\_)

class WebSocketManager:  
&nbsp;&nbsp;&nbsp;&nbsp;def \_\_init\_\_(self):  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;\# Словарь для хранения сокетов по идентификаторам сессий  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.active\_connections: Dict\[str, WebSocket\] \= {}

&nbsp;&nbsp;&nbsp;&nbsp;async def connect(self, session\_id: str, websocket: WebSocket):  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;await websocket.accept()  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.active\_connections\[session\_id\] \= websocket  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;logger.info(f"Соединение {session\_id} установлено.")

&nbsp;&nbsp;&nbsp;&nbsp;def disconnect(self, session\_id: str):  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;if session\_id in self.active\_connections:  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;del self.active\_connections\[session\_id\]  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;logger.info(f"Соединение {session\_id} разорвано.")

&nbsp;&nbsp;&nbsp;&nbsp;async def send\_json\_message(self, message: dict, session\_id: str):  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;websocket \= self.active\_connections.get(session\_id)  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;if websocket:  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;try:  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;await websocket.send\_json(message)  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;except RuntimeError as e:  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;\# Обработка ситуаций, когда сокет уже закрыт на уровне ОС  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;logger.error(f"Невозможно отправить данные в {session\_id}: {e}")  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.disconnect(session\_id)

ws\_manager \= WebSocketManager()  
app \= FastAPI()

@app.websocket("/ws/agent/{session\_id}")  
async def agent\_websocket(websocket: WebSocket, session\_id: str):  
&nbsp;&nbsp;&nbsp;&nbsp;await ws\_manager.connect(session\_id, websocket)  
&nbsp;&nbsp;&nbsp;&nbsp;try:  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;while True:  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;\# Блокирующее (асинхронно) ожидание входящего сообщения  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;data \= await websocket.receive\_json()  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;\# Эмуляция асинхронного вызова AI-агента  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;\# Агент может отправлять токены, метаданные или запросы на подтверждение  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;async for event in process\_agent\_workflow(data\["prompt"\]):  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;await ws\_manager.send\_json\_message(event, session\_id)  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;  
&nbsp;&nbsp;&nbsp;&nbsp;except WebSocketDisconnect:  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;ws\_manager.disconnect(session\_id)  
&nbsp;&nbsp;&nbsp;&nbsp;except Exception as e:  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;logger.error(f"Глобальная ошибка в сокете {session\_id}: {e}")  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;ws\_manager.disconnect(session\_id)

### **Защита от векторов атак (CSWSH) и аутентификация**

Протокол WebSockets подвержен уязвимости Cross-Site WebSocket Hijacking (CSWSH). Спецификация WebSockets намеренно не ограничивается правилами Same-Origin Policy (SOP), которые защищают традиционные AJAX-запросы в браузерах35. Злоумышленник может создать вредоносный сайт, на котором размещен JavaScript-код, инициирующий WebSocket-соединение с целевым FastAPI-сервером (ws://api.example.com/chat). Если пользователь авторизован в системе, браузер автоматически прикрепит сессионные куки к запросу на установку соединения, и злоумышленник получит полный доступ к AI-чату жертвы35.

Для предотвращения CSWSH FastAPI-бэкенд должен реализовать строгую проверку заголовка Origin во время рукопожатия, до вызова метода accept()36. Если заголовок Origin отсутствует или не совпадает с белым списком разрешенных доменов, соединение должно быть немедленно отвергнуто с генерацией HTTP-ошибки 403 Forbidden35.

Вопрос аутентификации в WebSockets также требует нестандартных подходов. Браузерный API WebSocket не позволяет передавать кастомные HTTP-заголовки (например, Authorization: Bearer \<token\>)31. Разработчики вынуждены выбирать между передачей токена в параметрах URL (ws://.../?token=xyz), что приводит к утечке секретов в серверные логи, или использованием паттерна "Аутентификация первым сообщением" (First-Message Auth). При втором подходе сервер принимает соединение, устанавливает тайм-аут и ожидает, что первым текстовым сообщением клиент пришлет JSON с авторизационными данными. Если токен невалиден или время ожидания истекло, сервер закрывает сокет с кодом 400131.

## **Горизонтальное масштабирование и управление состоянием с Redis**

Реализация ConnectionManager, хранящая сокеты в обычных словарях Python, функциональна лишь в пределах одного системного процесса. В производственной среде приложения FastAPI запускаются с использованием нескольких рабочих процессов (workers) ASGI-сервера Uvicorn или Gunicorn. Более того, облачная архитектура Kubernetes подразумевает горизонтальное масштабирование за счет добавления новых реплик (Pods)33.

Процессы Uvicorn полностью изолированы друг от друга и не имеют общей оперативной памяти33. Возникает классическая проблема распределенных систем: если системное событие (например, завершение длительной фоновой обработки документа AI-моделью) происходит на Воркере А, а пользователь физически подключен через WebSocket к Воркеру Б, Воркер А не сможет отправить сообщение, так как в его локальном словаре нет нужного соединения31.

### **Интеграция Redis Pub/Sub**

Решением является внедрение брокера сообщений. Redis Pub/Sub (Publish/Subscribe) идеально подходит для координации WebSocket-серверов благодаря минимальным задержкам и простоте развертывания32. Архитектурная модель меняется: серверы больше не пытаются общаться напрямую. Вместо этого каждый процесс FastAPI подписывается на определенный канал в Redis. Когда любому воркеру нужно отправить сообщение клиенту, он публикует его в Redis. Redis мгновенно рассылает это сообщение всем подписанным воркерам. Каждый воркер проверяет свой локальный словарь active\_connections; тот воркер, который фактически удерживает сокет клиента, выполняет отправку33.

Для реализации этой схемы используется асинхронный клиент redis.asyncio. Жизненный цикл подключения к Redis должен управляться через механизм lifespan контекстных менеджеров FastAPI, что гарантирует корректное открытие и закрытие пула соединений при старте и остановке приложения42. Важно учитывать, что поскольку каждый воркер создает свой собственный пул соединений с Redis, параметр max\_connections должен настраиваться с учетом количества запущенных процессов, чтобы не исчерпать глобальные лимиты сервера баз данных44.

&nbsp;

&nbsp;

&nbsp;

Python

import json  
import asyncio  
import logging  
from typing import Dict  
from contextlib import asynccontextmanager  
from fastapi import FastAPI, WebSocket, WebSocketDisconnect  
import redis.asyncio as aioredis

logger \= logging.getLogger(\_\_name\_\_)

class RedisPubSubManager:  
&nbsp;&nbsp;&nbsp;&nbsp;def \_\_init\_\_(self, redis\_url: str):  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.redis\_url \= redis\_url  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.redis\_client \= None  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.pubsub \= None  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.local\_websockets: Dict\[str, WebSocket\] \= {}

&nbsp;&nbsp;&nbsp;&nbsp;async def connect(self):  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;\# Инициализация пула соединений  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.redis\_client \= await aioredis.from\_url(  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.redis\_url,&nbsp;  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;encoding="utf-8",&nbsp;  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;decode\_responses=True,  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;max\_connections=10  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;)  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.pubsub \= self.redis\_client.pubsub()  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;await self.pubsub.subscribe("global\_chat\_channel")  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;\# Фоновая задача прослушивания брокера  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;asyncio.create\_task(self.\_listen\_to\_redis())  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;logger.info("Успешное подключение к Redis Pub/Sub")

&nbsp;&nbsp;&nbsp;&nbsp;async def disconnect(self):  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;if self.pubsub:  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;await self.pubsub.unsubscribe()  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;await self.pubsub.close()  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;if self.redis\_client:  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;await self.redis\_client.aclose()

&nbsp;&nbsp;&nbsp;&nbsp;def register\_client(self, user\_id: str, websocket: WebSocket):  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.local\_websockets\[user\_id\] \= websocket

&nbsp;&nbsp;&nbsp;&nbsp;def unregister\_client(self, user\_id: str):  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.local\_websockets.pop(user\_id, None)

&nbsp;&nbsp;&nbsp;&nbsp;async def publish\_message(self, target\_user\_id: str, message: dict):  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;payload \= {  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"target\_user\_id": target\_user\_id,  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"message": message  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;}  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;await self.redis\_client.publish("global\_chat\_channel", json.dumps(payload))

&nbsp;&nbsp;&nbsp;&nbsp;async def \_listen\_to\_redis(self):  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;try:  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;async for message in self.pubsub.listen():  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;if message\["type"\] \== "message":  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;data \= json.loads(message\["data"\])  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;target \= data.get("target\_user\_id")  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;\# Если целевой клиент подключен к этому конкретному воркеру  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;if target in self.local\_websockets:  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;ws \= self.local\_websockets\[target\]  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;try:  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;await ws.send\_json(data.get("message"))  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;except Exception as e:  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;logger.error(f"Ошибка доставки сообщения: {e}")  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;except asyncio.CancelledError:  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;pass

\# Глобальный экземпляр менеджера  
redis\_manager \= RedisPubSubManager("redis://localhost:6379")

@asynccontextmanager  
async def lifespan(app: FastAPI):  
&nbsp;&nbsp;&nbsp;&nbsp;\# Установка соединения при запуске сервера  
&nbsp;&nbsp;&nbsp;&nbsp;await redis\_manager.connect()  
&nbsp;&nbsp;&nbsp;&nbsp;yield  
&nbsp;&nbsp;&nbsp;&nbsp;\# Очистка ресурсов при завершении  
&nbsp;&nbsp;&nbsp;&nbsp;await redis\_manager.disconnect()

app \= FastAPI(lifespan=lifespan)

Подобная архитектура полностью развязывает узлы системы (decoupling), позволяя балансировщикам нагрузки (например, Nginx) маршрутизировать соединения на любые доступные серверы по алгоритму Round Robin, не беспокоясь об утере контекста сообщений40.

## **Распределенное ограничение скорости (Rate Limiting)**

Вычислительная сложность генерации текста обуславливает высокую стоимость эксплуатации AI-моделей. Публичные веб\-чаты становятся уязвимыми для автоматизированных злоупотреблений (API Abuse) и DDoS-атак, способных нанести значительный финансовый ущерб45. Традиционные библиотеки ограничения скорости, хранящие счетчики в памяти приложения, не подходят для распределенных систем по тем же причинам, что и локальные словари WebSockets. Необходима реализация Rate Limiting на базе централизованного хранилища, такого как Redis46.

### **Выбор алгоритма: Скользящее окно (Sliding Window Log)**

Наиболее распространенный алгоритм "Фиксированное окно" (Fixed Window) обладает существенным недостатком: он подвержен всплескам трафика на границе временных интервалов. Если лимит установлен в 10 запросов в минуту, пользователь может отправить 10 запросов на 59-й секунде и еще 10 запросов на 1-й секунде следующей минуты, фактически совершив 20 запросов за 2 секунды, что перегрузит LLM-провайдера47.

Алгоритм "Лог скользящего окна" (Sliding Window Log) решает эту проблему. В Redis для каждого пользователя создается структура Sorted Set (упорядоченное множество). При поступлении запроса его временная метка (timestamp в миллисекундах) добавляется во множество. Затем из множества удаляются все метки, которые старше текущего размера окна (например, старше 60 секунд). Оставшееся количество элементов во множестве равно реальному числу запросов в текущем скользящем окне. Если это число меньше установленного лимита, запрос разрешается45.

### **Атомарность через Lua-скрипты**

Поскольку проверка и обновление счетчиков в Redis требуют выполнения нескольких последовательных команд (ZREMRANGEBYSCORE, ZCARD, ZADD), возникает риск состояний гонки (race conditions) при параллельной обработке множества запросов от одного пользователя. Для обеспечения строгой атомарности вся логика инкапсулируется в Lua-скрипт. Сервер Redis выполняет скрипты атомарно в своем единственном основном потоке, блокируя другие операции до завершения скрипта, что гарантирует целостность данных45.

&nbsp;

&nbsp;

&nbsp;

Lua

\-- lua\_sliding\_window.lua  
local key \= KEYS\[1\]  
local current\_time \= tonumber(ARGV\[1\])  
local window\_size \= tonumber(ARGV\[2\])  
local limit \= tonumber(ARGV\[3\])

\-- Удаляем запросы, вышедшие за пределы скользящего окна  
local window\_start \= current\_time \- window\_size  
redis.call("ZREMRANGEBYSCORE", key, "-inf", window\_start)

\-- Получаем количество запросов в текущем окне  
local request\_count \= redis.call("ZCARD", key)

if request\_count \>= limit then  
&nbsp;&nbsp;&nbsp;&nbsp;return 0 \-- Лимит превышен  
end

\-- Добавляем текущий запрос (значение и счетчик \- это timestamp)  
\-- Используем случайный суффикс, чтобы элементы были уникальными  
redis.call("ZADD", key, current\_time, current\_time .. "\_" .. math.random())  
\-- Устанавливаем время жизни ключа (TTL) равным размеру окна для очистки памяти  
redis.call("EXPIRE", key, window\_size)

return 1 \-- Запрос одобрен

Для оптимизации сетевого трафика FastAPI-приложение не должно передавать текст скрипта при каждом запросе. Скрипт загружается в кеш Redis один раз с помощью команды SCRIPT LOAD, после чего вызывается по его SHA1-хешу с использованием команды EVALSHA. Логика проверки легко интегрируется в систему зависимостей (Dependencies) FastAPI, позволяя защищать отдельные эндпоинты одной строкой кода45.

## **Производительность, противодавление и фоновые задачи**

Разработка масштабируемого чата требует тщательного профилирования асинхронного кода. Некорректная работа с циклом событий (Event Loop) способна нивелировать все преимущества ASGI-архитектуры.

### **Пулинг соединений и HTTP/2**

При перенаправлении запросов к внешним провайдерам (OpenAI, Anthropic) критической ошибкой является создание нового объекта httpx.AsyncClient для каждого запроса. Установка TCP-соединения и TLS-рукопожатие занимают существенное время. Экземпляр клиента должен создаваться глобально при запуске приложения с настройкой параметров пула соединений (max\_connections, max\_keepalive\_connections) и включенной поддержкой HTTP/2. Это устраняет блокировку заголовка линии (head-of-line blocking) и кардинально снижает задержку TTFT51.

### **Противодавление (Backpressure)**

Потоковая передача данных сопряжена с риском переполнения буферов. Если локальная модель (Ollama) генерирует токены быстрее, чем клиент (на медленном мобильном интернете) способен их принимать, данные начинают скапливаться в выходных буферах FastAPI. Учитывая, что протокол SSE не имеет встроенных механизмов противодавления для сигнализации серверу о необходимости снизить скорость18, это приводит к утечкам памяти и потенциальному падению контейнера по превышению лимитов (OOMKilled)52.

Для управления нагрузкой на саму AI-модель применяются семафоры asyncio.Semaphore. Ограничение количества одновременных задач генерации на уровне FastAPI предотвращает лавинообразное нарастание нагрузки на GPU или сторонние API, аккуратно помещая избыточные запросы в очередь или отклоняя их с кодом 503 Service Unavailable51. Дополнительно необходимо избегать синхронных вызовов функций (например, синхронных коннекторов баз данных SQLAlchemy без поддержки async) внутри генераторов, так как они полностью блокируют поток выполнения и останавливают отправку токенов всем остальным клиентам54.

### **Управление фоновыми задачами**

Зачастую после завершения диалога требуется выполнить отложенные операции: суммаризацию беседы, расчет биллинга или индексацию векторной базы данных. FastAPI предоставляет инструмент BackgroundTasks, который позволяет поставить функцию в очередь на выполнение сразу после того, как HTTP-ответ был отправлен клиенту56.

Важно понимать разницу между BackgroundTasks и ручным вызовом asyncio.create\_task(). Если разработчик запускает задачу через create\_task и не сохраняет жесткую ссылку (strong reference) на полученный объект, встроенный в Python сборщик мусора (Garbage Collector) может уничтожить эту задачу прямо в процессе её выполнения, что приведет к непредсказуемой потере данных58. Объект BackgroundTasks безопасно инкапсулирует эти ссылки.

Однако, фоновые задачи FastAPI выполняются в оперативной памяти процесса. Если Uvicorn будет перезапущен (например, при масштабировании кластера Kubernetes), все невыполненные фоновые задачи будут утеряны58. Для задач, критичных к потере данных, архитектура должна предусматривать использование надежных очередей сообщений (Celery, RQ) и постоянного хранилища58. Кроме того, при использовании инструментов профилирования (OpenTelemetry) для отслеживания фоновых задач требуется явная передача контекста (Context Propagation), поскольку задача выполняется вне жизненного цикла родительского HTTP-запроса, и спаны (spans) могут быть утеряны61.

## **Заключение**

Создание масштабируемой и отказоустойчивой инфраструктуры веб\-чата для AI-моделей на базе FastAPI требует глубокого понимания механик транспортных протоколов и асинхронного программирования. Выбор между Server-Sent Events и WebSockets должен опираться на архитектурные потребности: SSE идеально справляется с потоковой передачей текста с минимальными затратами ресурсов, в то время как WebSockets необходимы для сложных двунаправленных агентов. Внедрение брокеров сообщений (Redis Pub/Sub) для маршрутизации, применение атомарных алгоритмов ограничения скорости на Lua для защиты от злоупотреблений, а также строгий контроль за жизненным циклом фоновых задач и транзакций баз данных формируют фундамент высокопроизводительной системы. Использование неблокирующих подходов, устранение паразитной буферизации на уровне прокси-серверов и переиспользование сетевых соединений позволяют достичь минимальных показателей задержки, обеспечивая отзывчивый пользовательский опыт при взаимодействии с генеративным искусственным интеллектом.

#### **Источники**

> 1. Real-time OpenAI response streaming with FastAPI \- Sevalla, [https://sevalla.com/blog/real-time-openai-streaming-fastapi/](https://sevalla.com/blog/real-time-openai-streaming-fastapi/)  
> 2. Streaming Locally Deployed LLM Responses Using FastAPI, [https://stackademic.com/blog/streaming-llm-responses-using-fastapi-deb575554397](https://stackademic.com/blog/streaming-llm-responses-using-fastapi-deb575554397)  
> 3. Streaming Agent State with LangGraph \- Focused.io, [https://focused.io/lab/streaming-agent-state-with-langgraph](https://focused.io/lab/streaming-agent-state-with-langgraph)  
> 4. FastAPI Server-Sent Events for LLM Streaming: Smooth Tokens, [https://medium.com/@2nick2patel2/fastapi-server-sent-events-for-llm-streaming-smooth-tokens-low-latency-1b211c94cff5](https://medium.com/@2nick2patel2/fastapi-server-sent-events-for-llm-streaming-smooth-tokens-low-latency-1b211c94cff5)  
> 5. STREAMING RESPONSE IN ANTHROPIC API (Claude) \- Medium, [https://medium.com/@dynamzee./streaming-response-in-anthropic-api-claude-b9444e95a57e?sharedUserId=dynamzee](https://medium.com/@dynamzee./streaming-response-in-anthropic-api-claude-b9444e95a57e?sharedUserId=dynamzee)  
> 6. FastAPI: async Python APIs with auto-generated OpenAPI | KERN-IT, [https://www.kern-it.be/en/definitions/fastapi/](https://www.kern-it.be/en/definitions/fastapi/)  
> 7. Concurrency and async / await \- FastAPI, [https://fastapi.tiangolo.com/async/](https://fastapi.tiangolo.com/async/)  
> 8. Streaming in FastAPI: SSE vs WebSockets vs Polling \- Faizan Nadeem, [https://faaaizan.space/blogs/fastapi-sse-vs-websockets/](https://faaaizan.space/blogs/fastapi-sse-vs-websockets/)  
> 9. A tech breakdown of Server-Sent Events vs WebSockets \- Neciu Dan, [https://neciudan.dev/sse-vs-websockets](https://neciudan.dev/sse-vs-websockets)  
> 10. How to Implement WebSockets in FastAPI \- OneUptime, [https://oneuptime.com/blog/post/2026-02-02-fastapi-websockets/view](https://oneuptime.com/blog/post/2026-02-02-fastapi-websockets/view)  
> 11. Polling vs SSE vs Websockets: which approach use the least workers?, [https://www.reddit.com/r/FastAPI/comments/1if6o84/polling\_vs\_sse\_vs\_websockets\_which\_approach\_use/](https://www.reddit.com/r/FastAPI/comments/1if6o84/polling_vs_sse_vs_websockets_which_approach_use/)  
> 12. SSE vs WebSocket vs REST API for Live AI (2026) \- stackcone, [https://stackcone.com/blog/posts/sse-websocket-rest-api-compared/](https://stackcone.com/blog/posts/sse-websocket-rest-api-compared/)  
> 13. WebSocket vs Server-Sent Events \- Key Differences \- GetStream.io, [https://getstream.io/blog/websocket-sse/](https://getstream.io/blog/websocket-sse/)  
> 14. WebSocket vs SSE Benchmark: SSE Uses 40% Less Memory at, [https://rexai.top/en/tutorials/rust/sse-vs-websocket-guide/](https://rexai.top/en/tutorials/rust/sse-vs-websocket-guide/)  
> 15. WebSocket vs SSE: How to choose for real-time apps \- Vercel, [https://vercel.com/i/websocket-vs-server-sent-events](https://vercel.com/i/websocket-vs-server-sent-events)  
> 16. Server-Sent Events Beat WebSockets for 95% of Real-Time Apps, [https://dev.to/polliog/server-sent-events-beat-websockets-for-95-of-real-time-apps-heres-why-a4l](https://dev.to/polliog/server-sent-events-beat-websockets-for-95-of-real-time-apps-heres-why-a4l)  
> 17. Real-Time Notifications in Python: Using SSE with FastAPI \- Medium, [https://medium.com/@inandelibas/real-time-notifications-in-python-using-sse-with-fastapi-1c8c54746eb7](https://medium.com/@inandelibas/real-time-notifications-in-python-using-sse-with-fastapi-1c8c54746eb7)  
> 18. AI Token Streaming: From SSE to Durable Sessions \- WebSocket.org, [https://websocket.org/guides/use-cases/ai-streaming/](https://websocket.org/guides/use-cases/ai-streaming/)  
> 19. LLM Streaming Tutorial: SSE in Python Step-by-Step, [https://machinelearningplus.com/gen-ai/llm-streaming-python/](https://machinelearningplus.com/gen-ai/llm-streaming-python/)  
> 20. Langchain with fastapi stream example \- GitHub Gist, [https://gist.github.com/ninely/88485b2e265d852d3feb8bd115065b1a](https://gist.github.com/ninely/88485b2e265d852d3feb8bd115065b1a)  
> 21. AI: Ollama with FastAPI \- Medium, [https://medium.com/@anjanikumar\_47235/ai-ollama-with-fastapi-703cd5d26152](https://medium.com/@anjanikumar_47235/ai-ollama-with-fastapi-703cd5d26152)  
> 22. 51 Streaming LLM Responses from Python with Ollama and httpx, [https://www.youtube.com/watch?v=WxnAXwomv00](https://www.youtube.com/watch?v=WxnAXwomv00)  
> 23. Building a Local LLM API Server with Ollama and FastAPI, [https://dev.to/ayinedjimi-consultants/building-a-local-llm-api-server-with-ollama-and-fastapi-2bpk](https://dev.to/ayinedjimi-consultants/building-a-local-llm-api-server-with-ollama-and-fastapi-2bpk)  
> 24. FastAPI StreamingResponse buffers LLM tokens until completion, [https://stackoverflow.com/questions/79952304/fastapi-streamingresponse-buffers-llm-tokens-until-completion-when-consumed-by-n](https://stackoverflow.com/questions/79952304/fastapi-streamingresponse-buffers-llm-tokens-until-completion-when-consumed-by-n)  
> 25. How I Implemented End-to-End SSE Streaming: From LLM to, [https://dev.to/martin\_palopoli/how-i-implemented-end-to-end-sse-streaming-from-llm-to-browser-through-nginx-4bjo](https://dev.to/martin_palopoli/how-i-implemented-end-to-end-sse-streaming-from-llm-to-browser-through-nginx-4bjo)  
> 26. Tutorial: Stream LLM Responses from a FastAPI Backend \- CallMissed, [https://www.callmissed.com/blog/tutorial-stream-llm-fastapi](https://www.callmissed.com/blog/tutorial-stream-llm-fastapi)  
> 27. Stop Burning CPU on Dead FastAPI Streams \- Jason Cameron, [https://jasoncameron.dev/posts/fastapi-cancel-on-disconnect](https://jasoncameron.dev/posts/fastapi-cancel-on-disconnect)  
> 28. Implementing Server-Sent Events (SSE) in FastAPI \- Toby Devlin, [https://tobydevlin.com/blog/sse-server-sent-events-in-fastapi/](https://tobydevlin.com/blog/sse-server-sent-events-in-fastapi/)  
> 29. Client disconnect while streaming response \- exits dependencies, [https://github.com/fastapi/fastapi/discussions/14552](https://github.com/fastapi/fastapi/discussions/14552)  
> 30. python asyncio \- how to wait for a cancelled shielded task?, [https://stackoverflow.com/questions/52505794/python-asyncio-how-to-wait-for-a-cancelled-shielded-task](https://stackoverflow.com/questions/52505794/python-asyncio-how-to-wait-for-a-cancelled-shielded-task)  
> 31. FastAPI WebSocket Production Guide: Building Bidirectional, [https://tomodahinata.com/en/blog/fastapi-websockets-realtime-production-guide](https://tomodahinata.com/en/blog/fastapi-websockets-realtime-production-guide)  
> 32. Scaling WebSockets with PUB/SUB using Python, Redis & FastAPI, [https://medium.com/@nandagopal05/scaling-websockets-with-pub-sub-using-python-redis-fastapi-b16392ffe291](https://medium.com/@nandagopal05/scaling-websockets-with-pub-sub-using-python-redis-fastapi-b16392ffe291)  
> 33. WebSocket with FastAPI: Async Connections & Scaling, [https://websocket.org/guides/frameworks/fastapi/](https://websocket.org/guides/frameworks/fastapi/)  
> 34. WebSocket Rooms & Broadcasting | Advanced FastAPI Patterns, [https://www.fastapiinteractive.com/fastapi-advanced-patterns/04-websocket-advanced](https://www.fastapiinteractive.com/fastapi-advanced-patterns/04-websocket-advanced)  
> 35. Websocket hijacking vulnerability · Issue \#128 \- GitHub, [https://github.com/miguelgrinberg/python-engineio/issues/128](https://github.com/miguelgrinberg/python-engineio/issues/128)  
> 36. Cross-Site WebSocket Hijacking (CSWSH) \- InfoSec Write-ups, [https://infosecwriteups.com/cross-site-websocket-hijacking-cswsh-ce2a6b0747fc](https://infosecwriteups.com/cross-site-websocket-hijacking-cswsh-ce2a6b0747fc)  
> 37. Cross-site WebSocket hijacking | Web Security Academy, [https://portswigger.net/web-security/websockets/cross-site-websocket-hijacking](https://portswigger.net/web-security/websockets/cross-site-websocket-hijacking)  
> 38. Cross-Site Websocket Hijacking (CSWSH) \- Praetorian, [https://www.praetorian.com/blog/cross-site-websocket-hijacking-cswsh/](https://www.praetorian.com/blog/cross-site-websocket-hijacking-cswsh/)  
> 39. How to Build WebSocket Servers with FastAPI and Redis \- OneUptime, [https://oneuptime.com/blog/post/2026-01-25-websocket-servers-fastapi-redis/view](https://oneuptime.com/blog/post/2026-01-25-websocket-servers-fastapi-redis/view)  
> 40. Scaling Pub/Sub with WebSockets and Redis \- Ably Realtime, [https://ably.com/blog/scaling-pub-sub-with-websockets-and-redis](https://ably.com/blog/scaling-pub-sub-with-websockets-and-redis)  
> 41. Developing WebSocket for Horizontal Scaling: Using Redis as, [https://blog.stackademic.com/developing-websocket-for-horizontal-scaling-using-redis-as-message-queue-a97cabd769d7](https://blog.stackademic.com/developing-websocket-for-horizontal-scaling-using-redis-as-message-queue-a97cabd769d7)  
> 42. Lifespan Events \- FastAPI, [https://fastapi.tiangolo.com/advanced/events/](https://fastapi.tiangolo.com/advanced/events/)  
> 43. FastAPI connect to Redis Pubsub and listen for messages on startup, [https://gist.github.com/artemonsh/ec1df88c6f0f5ee9cf40fe39914dbef5](https://gist.github.com/artemonsh/ec1df88c6f0f5ee9cf40fe39914dbef5)  
> 44. Best practices for handling Redis connection pooling in FastAPI, [https://www.reddit.com/r/learnpython/comments/1u5e99c/best\_practices\_for\_handling\_redis\_connection/](https://www.reddit.com/r/learnpython/comments/1u5e99c/best_practices_for_handling_redis_connection/)  
> 45. Redis and Lua Powered Sliding Window Rate Limiter \- Halodoc Blog, [https://blogs.halodoc.io/taming-the-traffic-redis-and-lua-powered-sliding-window-rate-limiter-in-action/](https://blogs.halodoc.io/taming-the-traffic-redis-and-lua-powered-sliding-window-rate-limiter-in-action/)  
> 46. FastAPI Rate Limiter Example \- GitHub, [https://github.com/photon-collider/rate-limiter-example](https://github.com/photon-collider/rate-limiter-example)  
> 47. How to Implement Sliding Window Rate Limiting with Redis, [https://oneuptime.com/blog/post/2026-03-31-redis-how-to-implement-sliding-window-rate-limiting-with-redis/view](https://oneuptime.com/blog/post/2026-03-31-redis-how-to-implement-sliding-window-rate-limiting-with-redis/view)  
> 48. Build 5 Rate Limiters with Redis: Algorithm Comparison Guide, [https://redis.io/tutorials/howtos/ratelimiting/](https://redis.io/tutorials/howtos/ratelimiting/)  
> 49. Implementing a Rate Limiter with FastAPI and Redis \- Bryan Anthonio, [https://bryananthonio.com/blog/implementing-rate-limiter-fastapi-redis/](https://bryananthonio.com/blog/implementing-rate-limiter-fastapi-redis/)  
> 50. Build a Sliding Window Rate Limiter with Redis \+ Lua \- YouTube, [https://www.youtube.com/watch?v=d7ef1qfD0FM](https://www.youtube.com/watch?v=d7ef1qfD0FM)  
> 51. 8 FastAPI Tricks for Low-Latency LLM Backends | by Bhagya Rana, [https://medium.com/@bhagyarana80/8-fastapi-tricks-for-low-latency-llm-backends-2831e3ee35d8](https://medium.com/@bhagyarana80/8-fastapi-tricks-for-low-latency-llm-backends-2831e3ee35d8)  
> 52. Chasing a Memory 'Leak' in our Async FastAPI Service, [https://build.betterup.com/chasing-a-memory-leak-in-our-async-fastapi-service-how-jemalloc-fixed-our-rss-creep/](https://build.betterup.com/chasing-a-memory-leak-in-our-async-fastapi-service-how-jemalloc-fixed-our-rss-creep/)  
> 53. Control buffering and backpressure when slow clients consume, [https://llmapireliability.com/posts/backpressure-for-llm-streaming-gateways/](https://llmapireliability.com/posts/backpressure-for-llm-streaming-gateways/)  
> 54. The Hidden Bottleneck in LLM Streaming \- Newline.co, [https://www.newline.co/@LouisSanna/the-hidden-bottleneck-in-llm-streaming-function-calls-and-how-to-fix-it--3c77b076](https://www.newline.co/@LouisSanna/the-hidden-bottleneck-in-llm-streaming-function-calls-and-how-to-fix-it--3c77b076)  
> 55. Stop Using async/await Blindly in FastAPI | by ANAMIKA GUPTA, [https://medium.com/@anamikarecsonbhadra/stop-using-async-await-blindly-in-fastapi-6bcf7749e160](https://medium.com/@anamikarecsonbhadra/stop-using-async-await-blindly-in-fastapi-6bcf7749e160)  
> 56. Background Tasks \- FastAPI, [https://fastapi.tiangolo.com/tutorial/background-tasks/](https://fastapi.tiangolo.com/tutorial/background-tasks/)  
> 57. Understanding Pitfalls of Async Task Management in FastAPI, [https://leapcell.io/blog/understanding-pitfalls-of-async-task-management-in-fastapi-requests](https://leapcell.io/blog/understanding-pitfalls-of-async-task-management-in-fastapi-requests)  
> 58. Python Background Tasks — Asyncio Traps, FastAPI & Celery (2026), [https://dev.to/kaushikcoderpy/python-background-tasks-asyncio-traps-fastapi-celery-2026-381i](https://dev.to/kaushikcoderpy/python-background-tasks-asyncio-traps-fastapi-celery-2026-381i)  
> 59. FastAPI with asyncio | Running long running background tasks, [https://stackoverflow.com/questions/79060473/fastapi-with-asyncio-running-long-running-background-tasks](https://stackoverflow.com/questions/79060473/fastapi-with-asyncio-running-long-running-background-tasks)  
> 60. FastAPI Background Tasks at Scale: Handling 1M+ Asynchronous, [https://medium.com/@bhagyarana80/fastapi-background-tasks-at-scale-handling-1m-asynchronous-side-jobs-d5920f14a473](https://medium.com/@bhagyarana80/fastapi-background-tasks-at-scale-handling-1m-asynchronous-side-jobs-d5920f14a473)  
> 61. How to Trace FastAPI Background Tasks with OpenTelemetry Spans, [https://oneuptime.com/blog/post/2026-02-06-trace-fastapi-background-tasks-opentelemetry/view](https://oneuptime.com/blog/post/2026-02-06-trace-fastapi-background-tasks-opentelemetry/view)