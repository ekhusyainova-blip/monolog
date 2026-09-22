# a_content.py
# Тема: chat
# Папка: аварийный слой (A_content)

import time
import httpx
import data_chat

def call_a_content(event):
    provider = next((p for p in data_chat.PROVIDERS if data_chat.KEYS.get(p)), None)
    if not provider:
        return None
    cfg = data_chat.PROVIDERS[provider]
    key = [k for k in data_chat.KEYS[provider] if k][0]
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    system = data_chat.PROMPTS.get("layer_a_content", "Ты — Monolog, аварийный.")
    body = {
        "model": cfg["model"],
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": event.get("text", "")},
        ],
        "temperature": data_chat.SETTINGS["temperature"],
        "max_tokens": data_chat.SETTINGS["max_tokens"],
    }
    with httpx.Client(timeout=data_chat.SETTINGS["timeout"]) as c:
        r = c.post(cfg["url"], headers=headers, json=body)
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]

@data_chat.on("need_a_content")
def handle(data):
    event = data.get("event", {})
    try:
        answer = call_a_content(event)
    except Exception as e:
        answer = f"[заглушка] {e}"
    output = {
        "vars": {"text": answer or "[заглушка]"},
        "routes": [{"to": "user"}],
        "silence": False,
        "prompts_new": None,
        "a_content": True,
    }
    data_chat.EVENTS.append({
        "ok": True,
        "data": {"output": output, "provider": "a_content"},
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    })