# chat_b_chat.py
# Тема: chat
# Слой: B (условие)

from chat_a_chat import on, emit, PROMPTS, SETTINGS

def when_chat_active(event: dict) -> bool:
    return bool((event.get("text") or "").strip())

def build_request(event: dict, context: list) -> dict:
    system = "\n".join([
        PROMPTS["layer_a"],
        PROMPTS["layer_b"],
        PROMPTS["layer_c"],
        PROMPTS["layer_d"],
    ])
    messages = [{"role": "system", "content": system}]
    for msg in (context or [])[-20:]:
        if isinstance(msg, dict) and "role" in msg and "content" in msg:
            messages.append(msg)
    messages.append({"role": "user", "content": event["text"]})
    return {
        "messages": messages,
        "temperature": SETTINGS["temperature"],
        "max_tokens": SETTINGS["max_tokens"],
    }

@on("user_message")
def handle_user_message(event: dict):
    if not when_chat_active(event):
        return
    context = event.get("context") or []
    payload = build_request(event, context)
    emit("request_built", {"event": event, "payload": payload})

# B · импорт C в конце
import chat_c_chat