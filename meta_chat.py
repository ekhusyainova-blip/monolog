# meta_chat.py — мета блока чата AI Monolog
# Слой D. Решает, что выводить. Наполняет EVENTS, откуда забирает A.

import time
import uuid
from interpret_chat import on, emit, SEND
from data_chat import MESSAGES, SETTINGS, PROVIDERS, KEYS, PROMPTS, CONTEXTS

UI = {"view": "chat", "streaming": False, "buffer": ""}

@on("request_ready")
def on_request_ready(payload):
    UI["streaming"] = True
    UI["buffer"] = ""
    emit("save_user", {"text": payload.get("text", ""), "id": uuid.uuid4().hex[:12], "ts": int(time.time())})

@on("chunk")
def on_chunk(payload):
    UI["buffer"] += payload.get("text", "")

@on("stream_finished")
def on_stream_finished(payload):
    UI["streaming"] = False
    SEND("status", {"kind": "stream", "state": "end"})
    emit("save_assistant", {"text": UI["buffer"], "id": uuid.uuid4().hex[:12], "ts": int(time.time())})

@on("message_saved")
def on_message_saved(msg):
    SEND("message", msg)

@on("error")
def on_error(payload):
    SEND("error", payload)

@on("retry")
def on_retry(payload):
    SEND("status", {"kind": "retry"})