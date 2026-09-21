# chat_c_chat.py
# Тема: chat
# Слой: C (решение)

import time
import httpx

from chat_a_chat import on, emit, PROVIDERS, SETTINGS, KEYS

_rotation = {}
_exhausted = {}

def has_keys(provider: str) -> bool:
    return bool([k for k in KEYS.get(provider, []) if k])

def pick_provider(preferred: str = None) -> str:
    if preferred and has_keys(preferred):
        return preferred
    for name in SETTINGS["provider_order"]:
        if has_keys(name):
            return name
    raise ValueError("Нет доступных провайдеров")

def pick_key(provider: str) -> str:
    keys = [k for k in KEYS.get(provider, []) if k]
    if not keys:
        raise ValueError(f"Нет ключей для {provider}")
    now = time.time()
    exhausted = _exhausted.get(provider, {})
    active = [k for k in keys if exhausted.get(k, 0) < now]
    if not active:
        _exhausted[provider] = {}
        active = keys
    idx = _rotation.get(provider, 0) % len(active)
    _rotation[provider] = idx + 1
    return active[idx]

def mark_exhausted(provider: str, key: str) -> None:
    _exhausted.setdefault(provider, {})[key] = time.time() + SETTINGS["cooldown_sec"]

def _headers(provider: str, key: str) -> dict:
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }
    if provider == "openrouter":
        headers["HTTP-Referer"] = "https://monolog.app"
        headers["X-Title"] = "Monolog"
    return headers

def call_provider(provider: str, payload: dict) -> dict:
    key = pick_key(provider)
    cfg = PROVIDERS[provider]
    headers = _headers(provider, key)
    body = dict(payload)
    body["model"] = cfg["model"]
    with httpx.Client(timeout=SETTINGS["timeout"]) as client:
        r = client.post(cfg["url"], headers=headers, json=body)
        if r.status_code == 429:
            mark_exhausted(provider, key)
        r.raise_for_status()
        return r.json()

@on("request_built")
def handle_request_built(data: dict):
    event = data["event"]
    payload = data["payload"]
    try:
        provider = pick_provider(event.get("provider"))
    except ValueError as e:
        emit("answer_ready", {"error": str(e)})
        return
    t0 = time.time()
    try:
        result = call_provider(provider, payload)
        answer = result["choices"][0]["message"]["content"]
        emit("answer_ready", {
            "answer": answer,
            "provider": provider,
            "elapsed": time.time() - t0,
        })
    except Exception as e:
        emit("answer_ready", {"error": str(e)})

# C · импорт D в конце
import chat_d_chat