# interpret_chat.py — интерпретация блока чата AI Monolog
# Слой B. Шина событий + выбор провайдера и ключа.
# Условия — в data_chat (ERROR_RULES, SELECT_RULES, STATES).

import time
from data_chat import (
    PROVIDERS, KEYS, PROMPTS, PROMPT_ORDER, MESSAGES,
    ERROR_RULES, SELECT_RULES, STATES,
)

HANDLERS = {}
EVENTS = []

def on(event):
    def deco(fn):
        HANDLERS.setdefault(event, []).append(fn)
        return fn
    return deco

def emit(event, payload=None):
    for fn in HANDLERS.get(event, []):
        fn(payload or {})

def SEND(event_type, data):
    EVENTS.append({"type": event_type, "data": data})

def _alive_state(key):
    return key["state"] in STATES["alive"]

def _wait_state(key):
    return key["state"] in STATES["wait"] and time.time() >= key["cooldown_until"]

def _alive_key(key):
    return _alive_state(key) or _wait_state(key)

def _keys_of(pid):
    return [k for k in KEYS if k["provider_id"] == pid]

def _alive_provider(p):
    flags = [
        p["enabled"] or not SELECT_RULES["skip_disabled"],
        bool(p["base_url"]) or not SELECT_RULES["skip_empty_url"],
        bool(_keys_of(p["id"])) or not SELECT_RULES["skip_empty_keys"],
    ]
    return all(flags) and any(_alive_key(k) for k in _keys_of(p["id"]))

def pick_provider():
    live = [p for p in PROVIDERS if _alive_provider(p)]
    live.sort(key=lambda p: p[SELECT_RULES["sort_key"]])
    return live[0] if live else None

def pick_key(provider):
    alive = [k for k in _keys_of(provider["id"]) if _alive_key(k)]
    alive.sort(key=lambda k: k["last_used"])
    if alive:
        alive[0]["last_used"] = time.time()
    return alive[0] if alive else None

def active_prompt(slot):
    found = [p for p in PROMPTS if p["slot"] == slot and p["active"] and p["slot_enabled"] and p["text"].strip()]
    return found[0] if found else None

def build_system():
    parts = [active_prompt(s)["text"].strip() for s in PROMPT_ORDER if active_prompt(s)]
    return "\n\n".join(parts)

def build_messages():
    system = build_system()
    head = [{"role": "system", "content": system}] if system else []
    return head + [{"role": m["role"], "content": m["content"]} for m in MESSAGES]

@on("user_message")
def handle_user_message(payload):
    provider = pick_provider()
    key = pick_key(provider) if provider else None
    emit("request_ready", {
        "provider": provider,
        "key_id": key["id"] if key else "",
        "model": provider["model_default"] if provider else "",
        "messages": build_messages(),
        "text": payload.get("text", ""),
    }) if provider and key else SEND("error", {"msg": "нет живых провайдеров или ключей"})

@on("provider_fail")
def handle_provider_fail(payload):
    rule = ERROR_RULES.get(payload.get("status"), ERROR_RULES["default"])
    for k in KEYS:
        if k["id"] == payload.get("key_id"):
            k["state"] = "cooldown" if rule["action"] == "cooldown" else "exhausted"
            k["cooldown_until"] = time.time() + rule.get("seconds", 0)
    emit("retry", {"text": payload.get("text", "")})

@on("provider_ok")
def handle_provider_ok(payload):
    for k in KEYS:
        if k["id"] == payload.get("key_id"):
            k["state"] = "ok"
            k["cooldown_until"] = 0

# ================= ЗАГРУЗКА =================

import solve_chat