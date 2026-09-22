# solve_abcd.py
# Тема: chat
# Папка: ABCD-роутер
# Делает 4 вызова: A → B → C → D. Разные модели. Fallback при отказе.

import os
import time
import httpx
import data_chat

# Провайдеры и модели по слоям
LAYERS = {
    "a": {
        "primary": {
            "provider": "groq",
            "model": "qwen/qwen3.6-27b",
            "url": "https://api.groq.com/openai/v1/chat/completions",
            "env": "GROQ_API_KEYS",
            "browser_search": True,
        },
        "fallback": {
            "provider": "groq",
            "model": "openai/gpt-oss-120b",
            "url": "https://api.groq.com/openai/v1/chat/completions",
            "env": "GROQ_API_KEYS",
            "browser_search": True,
        },
    },
    "b": {
        "primary": {
            "provider": "cerebras",
            "model": "qwen-3.8-27b",
            "url": "https://api.cerebras.ai/v1/chat/completions",
            "env": "CEREBRAS_API_KEY",
        },
        "fallback": {
            "provider": "cerebras",
            "model": "gpt-oss-120b",
            "url": "https://api.cerebras.ai/v1/chat/completions",
            "env": "CEREBRAS_API_KEY",
        },
    },
    "c": {
        "primary": {
            "provider": "openrouter",
            "model": "deepseek/deepseek-r1:free",
            "url": "https://openrouter.ai/api/v1/chat/completions",
            "env": "OPENROUTER_API_KEY",
        },
        "fallback": {
            "provider": "sambanova",
            "model": "DeepSeek-V3.1",
            "url": "https://api.sambanova.ai/v1/chat/completions",
            "env": "SAMBANOVA_API_KEY",
        },
    },
    "d": {
        "primary": {
            "provider": "cerebras",
            "model": "gemma-4-31b",
            "url": "https://api.cerebras.ai/v1/chat/completions",
            "env": "CEREBRAS_API_KEY",
        },
        "fallback": {
            "provider": "sambanova",
            "model": "gpt-oss-120b",
            "url": "https://api.sambanova.ai/v1/chat/completions",
            "env": "SAMBANOVA_API_KEY",
        },
    },
}

_rotation = {}
_exhausted = {}

def pick_key(env_name):
    raw = os.getenv(env_name, "").strip()
    keys = [k.strip() for k in raw.split(",") if k.strip()] if raw else []
    if not keys:
        raise ValueError(f"Нет ключей для {env_name}")
    now = time.time()
    ex = _exhausted.get(env_name, {})
    active = [k for k in keys if ex.get(k, 0) < now] or keys
    idx = _rotation.get(env_name, 0) % len(active)
    _rotation[env_name] = idx + 1
    return active[idx]

def mark_exhausted(env_name, key):
    _exhausted.setdefault(env_name, {})[key] = time.time() + 65

def call_one(layer_cfg, messages, browser_search=False):
    env_name = layer_cfg["env"]
    key = pick_key(env_name)
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    if layer_cfg["provider"] == "openrouter":
        headers["HTTP-Referer"] = "https://monolog.app"
        headers["X-Title"] = "Monolog"
    body = {
        "model": layer_cfg["model"],
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": 2048,
    }
    if browser_search and layer_cfg.get("browser_search"):
        body["tools"] = [{"type": "browser_search"}]
        body["tool_choice"] = "required"
    with httpx.Client(timeout=180) as c:
        r = c.post(layer_cfg["url"], headers=headers, json=body)
        if r.status_code == 429:
            mark_exhausted(env_name, key)
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]

def call_layer(layer_name, messages, browser_search=False):
    cfg = LAYERS.get(layer_name)
    if not cfg:
        raise ValueError(f"Неизвестный слой: {layer_name}")
    try:
        return call_one(cfg["primary"], messages, browser_search=browser_search)
    except Exception as e:
        print(f"[solve_abcd] {layer_name} primary failed: {e}", flush=True)
    try:
        return call_one(cfg["fallback"], messages, browser_search=browser_search)
    except Exception as e:
        print(f"[solve_abcd] {layer_name} fallback failed: {e}", flush=True)
        raise

def build_messages(system, history, user_text):
    msgs = [{"role": "system", "content": system}]
    for m in (history or [])[-20:]:
        if isinstance(m, dict) and "role" in m and "content" in m:
            msgs.append(m)
    msgs.append({"role": "user", "content": user_text})
    return msgs

@data_chat.on("request_built")
def handle(data):
    event = data["event"]
    history = event.get("context") or []
    user_text = event["text"]
    prompts = data_chat.PROMPTS

    try:
        # A — анализ (с поиском)
        system_a = prompts.get("layer_a", "")
        analysis = call_layer("a", build_messages(system_a, history, user_text), browser_search=True)

        # B — противоречия
        system_b = prompts.get("layer_b", "")
        contradictions = call_layer("b", build_messages(system_b, history, analysis))

        # C — решение
        system_c = prompts.get("layer_c", "")
        solution = call_layer("c", build_messages(system_c, history, contradictions))

        # D — вывод
        system_d = prompts.get("layer_d", "")
        final = call_layer("d", build_messages(system_d, history, solution))

        data_chat.emit("answer_ready", {
            "answer": final,
            "provider": "abcd-chain",
            "elapsed": 0.0,
            "event": event,
        })

    except Exception as e:
        data_chat.emit("answer_failed", {"error": str(e), "event": event})