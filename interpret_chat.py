# interpret_chat.py
# Тема: chat
# Папка: B (базовый интерфейс)

import data_chat

def build_request(event):
    prompts = data_chat.PROMPTS
    settings = data_chat.SETTINGS
    system = "\n".join([
        prompts.get("layer_a", ""),
        prompts.get("layer_b", ""),
        prompts.get("layer_c", ""),
        prompts.get("layer_d", ""),
    ])
    messages = [{"role": "system", "content": system}]
    for m in (event.get("context") or [])[-20:]:
        if isinstance(m, dict) and "role" in m and "content" in m:
            messages.append(m)
    messages.append({"role": "user", "content": event["text"]})
    return {
        "messages": messages,
        "temperature": settings["temperature"],
        "max_tokens": settings["max_tokens"],
    }

@data_chat.on("user_message")
def handle(event):
    if not (event.get("text") or "").strip():
        return
    payload = build_request(event)
    data_chat.emit("request_built", {"event": event, "payload": payload})

import solve_chat