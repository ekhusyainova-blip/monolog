# meta_chat.py
# Тема: chat
# Папка: D (мета)

import time
import json
import re
from data_chat import on, EVENTS

def extract_json(text):
    if not text:
        return None
    t = text.strip()
    t = re.sub(r"```json", "", t, flags=re.IGNORECASE)
    t = t.replace("```", "").strip()
    a = t.find("{")
    b = t.rfind("}")
    if a < 0 or b < 0:
        return None
    try:
        return json.loads(t[a:b+1])
    except Exception:
        return None

def default_output(text=""):
    return {
        "text": text,
        "metrics": [],
        "style": {"theme": "dark", "density": "airy", "accent": "soft"},
        "modules": ["chat"],
        "navigation": {"where": "chat", "sphere_visible": False, "menu_available": True},
        "mode": "clarity",
        "screen": "conversation",
        "silence": False,
        "allow_leave": True,
    }

def build_response(answer, provider, elapsed):
    parsed = extract_json(answer)
    if parsed and isinstance(parsed, dict) and parsed.get("text"):
        output = parsed
    else:
        output = default_output(answer)
    return {
        "ok": True,
        "data": {
            "output": output,
            "provider": provider,
            "elapsed": round(elapsed, 3),
        },
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