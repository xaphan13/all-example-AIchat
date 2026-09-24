"""
AI Web Chat — минимальный, но production-ориентированный пример
веб-чата с AI-моделью на FastAPI.

Реализует ДВА способа доставки потокового ответа:
  1. WebSocket   — /ws/chat/{session_id}   (двусторонний, для полноценного чата)
  2. SSE (Server-Sent Events) — /api/chat/stream  (однонаправленный, проще
     для CDN/прокси, легко дебажить curl'ом)

Хранение истории диалога — в памяти процесса (SESSIONS). Для продакшена
замените на Redis / БД — см. README.md, раздел "Хранение состояния".
"""

import os
import json
import logging
from typing import AsyncGenerator

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from anthropic import AsyncAnthropic
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ai-web-chat")

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
MODEL_NAME = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")
MAX_HISTORY_MESSAGES = 30  # простая защита от неограниченного роста контекста/счёта

if not ANTHROPIC_API_KEY:
    raise RuntimeError(
        "Не задан ANTHROPIC_API_KEY. Скопируйте .env.example в .env и впишите ключ."
    )

client = AsyncAnthropic(api_key=ANTHROPIC_API_KEY)

# --------------------------------------------------------------------------
# Хранилище истории диалогов: {session_id: [{"role": ..., "content": ...}]}
# ВАЖНО: это in-memory-хранилище живёт только пока жив один процесс/воркер.
# Для нескольких воркеров/машин нужен внешний стор (Redis и т.п.).
# --------------------------------------------------------------------------
SESSIONS: dict[str, list[dict]] = {}


def get_history(session_id: str) -> list[dict]:
    return SESSIONS.setdefault(session_id, [])


def trim_history(history: list[dict]) -> None:
    if len(history) > MAX_HISTORY_MESSAGES:
        del history[: len(history) - MAX_HISTORY_MESSAGES]


app = FastAPI(title="AI Web Chat", version="1.0.0")

# В проде укажите конкретные домены вместо "*"
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
async def index() -> FileResponse:
    return FileResponse("static/index.html")


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


# ==========================================================================
# Вариант 1: WebSocket — рекомендуемый способ для полноценного чата
# ==========================================================================

@app.websocket("/ws/chat/{session_id}")
async def ws_chat(websocket: WebSocket, session_id: str) -> None:
    await websocket.accept()
    history = get_history(session_id)
    logger.info("WS connected: session=%s", session_id)

    try:
        while True:
            user_message = await websocket.receive_text()
            history.append({"role": "user", "content": user_message})

            assistant_text = ""
            try:
                async with client.messages.stream(
                    model=MODEL_NAME,
                    max_tokens=1024,
                    messages=history,
                ) as stream:
                    async for text_chunk in stream.text_stream:
                        assistant_text += text_chunk
                        await websocket.send_json(
                            {"type": "chunk", "content": text_chunk}
                        )
                await websocket.send_json({"type": "done"})
            except Exception as exc:  # noqa: BLE001 — хотим поймать любые ошибки SDK/сети
                logger.exception("Ошибка при обращении к модели")
                # откатываем последнее сообщение пользователя, раз ответа не будет
                history.pop()
                await websocket.send_json(
                    {"type": "error", "content": f"Ошибка модели: {exc}"}
                )
                continue

            history.append({"role": "assistant", "content": assistant_text})
            trim_history(history)

    except WebSocketDisconnect:
        logger.info("WS disconnected: session=%s", session_id)


# ==========================================================================
# Вариант 2: SSE — проще проходит через прокси/CDN, не нуждается в апгрейде
# протокола, легко тестировать через curl -N
# ==========================================================================

class ChatRequest(BaseModel):
    session_id: str
    message: str


@app.post("/api/chat/stream")
async def chat_stream(payload: ChatRequest) -> StreamingResponse:
    history = get_history(payload.session_id)
    history.append({"role": "user", "content": payload.message})

    async def event_generator() -> AsyncGenerator[str, None]:
        assistant_text = ""
        try:
            async with client.messages.stream(
                model=MODEL_NAME,
                max_tokens=1024,
                messages=history,
            ) as stream:
                async for text_chunk in stream.text_stream:
                    assistant_text += text_chunk
                    payload_json = json.dumps(
                        {"content": text_chunk}, ensure_ascii=False
                    )
                    yield f"data: {payload_json}\n\n"

            history.append({"role": "assistant", "content": assistant_text})
            trim_history(history)
            yield "event: done\ndata: {}\n\n"

        except Exception as exc:  # noqa: BLE001
            logger.exception("Ошибка при обращении к модели (SSE)")
            history.pop()
            error_json = json.dumps({"message": str(exc)}, ensure_ascii=False)
            yield f"event: error\ndata: {error_json}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
