# interpret_chat.py
# Тема: chat
# Папка: B (базовый интерфейс)

from data_chat import on, emit, PROMPTS, SETTINGS

def build_request(event):
    system = "\n".join([PROMPTS["layer_a"], PROMPTS["layer_b"], PROMPTS["layer_c"], PROMPTS["layer_d"], PROMPTS["layer_a_content"]])
    messages = [{"role": "system", "content": system}]
    for m in (event.get("context") or [])[-20:]:
        if isinstance(m, dict) and "role" in m and "content" in m:
            messages.append(m)
    messages.append({"role": "user", "content": event["text"]})
    return {
        "messages": messages,
        "temperature": SETTINGS["temperature"],
        "max_tokens": SETTINGS["max_tokens"],
    }

@on("user_message")
def handle(event):
    if not (event.get("text") or "").strip():
        return
    payload = build_request(event)
    emit("request_built", {"event": event, "payload": payload})

import solve_chat