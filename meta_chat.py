# meta_chat.py
# Тема: chat
# Папка: D (мета)

import time
from data_chat import on, EVENTS

def build_response(answer, provider, elapsed):
    return {
        "ok": True,
        "data": {"answer": answer, "provider": provider, "elapsed": round(elapsed, 3)},
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }

def build_error(cls, msg):
    return {
        "ok": False,
        "error": {"code": 500, "class": cls, "message": msg},
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }

@on("answer_ready")
def handle(data):
    if data.get("error"):
        EVENTS.append(build_error("provider", data["error"]))
        return
    EVENTS.append(build_response(
        data["answer"],
        data.get("provider", "unknown"),
        data.get("elapsed", 0.0),
    ))