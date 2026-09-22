# meta_chat.py
# Тема: chat
# Папка: D (мета, маршрутизатор)

import time
import json
import re
import data_chat

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
        "vars": {"text": text},
        "routes": [{"to": "user"}],
        "silence": False,
        "prompts_new": None,
    }

def apply_prompts(new):
    if not new or not isinstance(new, dict):
        return
    for k, v in new.items():
        if isinstance(v, str) and v.strip():
            data_chat.PROMPTS[k] = v

def build_response(parsed, provider, elapsed):
    if parsed and isinstance(parsed, dict) and ("vars" in parsed or "silence" in parsed):
        output = parsed
    else:
        output = default_output(parsed if isinstance(parsed, str) else "")
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

@data_chat.on("answer_ready")
def handle(data):
    answer = data.get("answer", "")
    parsed = extract_json(answer)
    if not parsed or not isinstance(parsed, dict):
        parsed = default_output(answer)
    if parsed.get("prompts_new"):
        apply_prompts(parsed.get("prompts_new"))
    data_chat.EVENTS.append(build_response(
        parsed,
        data.get("provider", "unknown"),
        data.get("elapsed", 0.0),
    ))

@data_chat.on("answer_failed")
def handle_failed(data):
    data_chat.emit("need_a_content", data)