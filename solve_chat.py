# solve_chat.py — решение чата AI Monolog Chat
# Слой C. Отправляет запрос, стримит ответ, режет на блоки.
# Слушает request_ready от interpret_chat. Чанки пишет через SEND.

import json
import httpx
from interpret_chat import on, emit, SEND
from data_chat import KEYS, MESSAGES

async def _stream_request(provider, key, model, messages):
    url = f"{provider['base_url']}/chat/completions"
    headers = {
        "Authorization": f"Bearer {key['value']}",
        "Content-Type": "application/json",
    }
    if provider["id"] == "openrouter":
        headers["HTTP-Referer"] = "https://ai-monolog.onrender.com"
        headers["X-Title"] = "AI Monolog Chat"
    body = {"model": model, "messages": messages, "stream": True}
    async with httpx.AsyncClient(timeout=120.0) as client:
        async with client.stream("POST", url, headers=headers, json=body) as r:
            if r.status_code != 200:
                return {"error": r.status_code}
            async for line in r.aiter_lines():
                if not line or not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                try:
                    obj = json.loads(data)
                except Exception:
                    continue
                delta = obj.get("choices", [{}])[0].get("delta", {})
                piece = delta.get("content", "")
                if piece:
                    SEND("chunk", {"text": piece})
    return {"ok": True}

def parse_blocks(text):
    blocks = []
    buf = ""
    i = 0
    while i < len(text):
        if text.startswith("```", i):
            if buf.strip():
                blocks.append({"type": "text", "content": buf})
                buf = ""
            j = text.find("\n", i + 3)
            lang = text[i + 3:j].strip() if j != -1 else ""
            end = text.find("```", j + 1) if j != -1 else -1
            if end == -1:
                buf += text[i:]
                break
            body = text[j + 1:end]
            btype = "json" if lang.lower() == "json" or (lang == "" and body.strip().startswith(("{", "["))) else "code"
            blocks.append({"type": btype, "lang": lang or "text", "content": body.rstrip("\n")})
            i = end + 3
        else:
            buf += text[i]
            i += 1
    if buf.strip():
        blocks.append({"type": "text", "content": buf})
    return blocks

@on("request_ready")
async def handle_request(payload):
    provider = payload["provider"]
    key = next((k for k in KEYS if k["id"] == payload["key_id"]), None)
    if not key:
        SEND("error", {"where": "solve", "msg": "ключ не найден"})
        return
    if not key["value"]:
        SEND("error", {"where": "solve", "msg": f"ключ {key['id']} пуст"})
        return
    SEND("status", {"kind": "stream", "state": "start", "provider_id": provider["id"], "key_id": key["id"]})
    result = await _stream_request(provider, key, payload["model"], payload["messages"])
    if "error" in result:
        emit("provider_fail", {"key_id": key["id"], "status": result["error"], "text": payload.get("text", "")})
        return
    emit("provider_ok", {"key_id": key["id"]})
    emit("stream_finished", {"provider_id": provider["id"], "key_id": key["id"]})

@on("save_assistant")
def handle_save(payload):
    raw = payload.get("text", "")
    blocks = parse_blocks(raw)
    msg = {
        "id": payload.get("id", ""),
        "role": "assistant",
        "content": raw,
        "blocks": blocks,
        "ts": payload.get("ts", 0),
        "provider_id": payload.get("provider_id", ""),
        "key_id": payload.get("key_id", ""),
    }
    MESSAGES.append(msg)
    emit("message_saved", msg)

@on("save_user")
def handle_save_user(payload):
    msg = {
        "id": payload.get("id", ""),
        "role": "user",
        "content": payload.get("text", ""),
        "blocks": [{"type": "text", "content": payload.get("text", "")}],
        "ts": payload.get("ts", 0),
        "provider_id": "",
        "key_id": "",
    }
    MESSAGES.append(msg)
    emit("message_saved", msg)