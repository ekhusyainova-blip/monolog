# chat_d_chat.py
# Тема: chat
# Слой: D (мета)

import time

from chat_a_chat import on, EVENTS

def build_response(answer: str, provider: str, elapsed: float) -> dict:
    return {
        "ok": True,
        "data": {
            "answer": answer,
            "provider": provider,
            "elapsed": round(elapsed, 3),
        },
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }

def build_error(cls: str, msg: str) -> dict:
    return {
        "ok": False,
        "error": {"code": 500, "class": cls, "message": msg},
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }

@on("answer_ready")
def handle_answer_ready(data: dict):
    if data.get("error"):
        EVENTS.append(build_error("provider", data["error"]))
        return
    EVENTS.append(build_response(
        data["answer"],
        data.get("provider", "unknown"),
        data.get("elapsed", 0.0),
    ))