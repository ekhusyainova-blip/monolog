# solve_chat.py
# Тема: chat
# Папка: C (модули)

import time
import httpx
import data_chat

_rotation = {}
_exhausted = {}

def pick_key(provider):
    keys = [k for k in data_chat.KEYS.get(provider, []) if k]
    if not keys:
        raise ValueError(f"Нет ключей для {provider}")
    now = time.time()
    ex = _exhausted.get(provider, {})
    active = [k for k in keys if ex.get(k, 0) < now] or keys
    idx = _rotation.get(provider, 0) % len(active)
    _rotation[provider] = idx + 1
    return active[idx]

def mark_exhausted(provider, key):
    _exhausted.setdefault(provider, {})[key] = time.time() + data_chat.SETTINGS["cooldown_sec"]

def call_provider(provider, payload):
    key = pick_key(provider)
    cfg = data_chat.PROVIDERS[provider]
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    body = dict(payload)
    body["model"] = cfg["model"]
    with httpx.Client(timeout=data_chat.SETTINGS["timeout"]) as c:
        r = c.post(cfg["url"], headers=headers, json=body)
        if r.status_code == 429:
            mark_exhausted(provider, key)
        r.raise_for_status()
        return r.json()

@data_chat.on("request_built")
def handle(data):
    event = data["event"]
    payload = data["payload"]
    provider = next((p for p in data_chat.PROVIDERS if data_chat.KEYS.get(p)), None)
    if not provider:
        data_chat.emit("answer_failed", {"error": "Нет доступных провайдеров", "event": event})
        return
    t0 = time.time()
    try:
        result = call_provider(provider, payload)
        answer = result["choices"][0]["message"]["content"]
        data_chat.emit("answer_ready", {
            "answer": answer,
            "provider": provider,
            "elapsed": time.time() - t0,
            "event": event,
        })
    except Exception as e:
        data_chat.emit("answer_failed", {"error": str(e), "event": event})

import meta_chat
import a_content