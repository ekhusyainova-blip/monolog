# meta_chat.py — мета чата AI Monolog Chat
# Слой D. Решает, что выводить. Мост между emit (внутренняя шина) и SEND (внешняя).
# Сам не выводит — кладёт в EVENTS, оттуда забирает data_chat.

import time
import uuid
from interpret_chat import on, emit, SEND, EVENTS
from data_chat import SETTINGS, UI_STATES, PROVIDERS, KEYS, PROMPTS, MESSAGES, CONTEXTS

# ---------- СОСТОЯНИЕ ИНТЕРФЕЙСА ----------

UI = {
    "view": "chat",
    "panel": "",
    "focus_msg": "",
    "show_repo": False,
    "streaming": False,
    "buffer": "",
    "current_provider": "",
    "current_key": "",
}

# ---------- СТРИМ ----------

@on("request_ready")
def on_request_ready(payload):
    UI["streaming"] = True
    UI["buffer"] = ""
    UI["current_provider"] = payload["provider"]["id"]
    UI["current_key"] = payload["key_id"]
    emit("save_user", {
        "text": payload.get("text", ""),
        "id": uuid.uuid4().hex[:12],
        "ts": int(time.time()),
    })

@on("chunk")
def on_chunk(payload):
    UI["buffer"] += payload.get("text", "")

@on("stream_finished")
def on_stream_finished(payload):
    raw = UI["buffer"]
    UI["streaming"] = False
    SEND("status", {"kind": "stream", "state": "end"})
    emit("save_assistant", {
        "text": raw,
        "id": uuid.uuid4().hex[:12],
        "ts": int(time.time()),
        "provider_id": payload.get("provider_id", ""),
        "key_id": payload.get("key_id", ""),
    })

# ---------- СОХРАНЕНИЕ СООБЩЕНИЙ ----------

@on("message_saved")
def on_message_saved(msg):
    SEND("message", msg)

# ---------- ОШИБКИ И РЕТРАЙ ----------

@on("error")
def on_error(payload):
    SEND("error", payload)

@on("retry")
def on_retry(payload):
    SEND("status", {"kind": "retry", "reason": payload.get("reason", ""), "status": payload.get("status", 0)})
    text = payload.get("text", "")
    if text:
        emit("user_message", {"text": text})

# ---------- СНАПШОТ ----------

def snapshot():
    return {
        "ui": dict(UI),
        "providers": PROVIDERS,
        "keys": [{k: v for k, v in key.items() if k != "value"} for key in KEYS],
        "prompts": PROMPTS,
        "slots": UI_STATES,
        "settings": SETTINGS,
        "contexts": CONTEXTS,
        "messages_count": len(MESSAGES),
    }

# ---------- УПРАВЛЕНИЕ ВИДОМ ----------

@on("set_view")
def on_set_view(payload):
    UI["view"] = payload.get("view", "chat")
    SEND("ui", {"kind": "view", "value": UI["view"]})

@on("set_panel")
def on_set_panel(payload):
    UI["panel"] = payload.get("panel", "")
    SEND("ui", {"kind": "panel", "value": UI["panel"]})