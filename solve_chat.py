# solve_chat.py — решение блока чата AI Monolog
# Слой C. Отправка запроса, стрим, разбор на блоки.

import json
import httpx
from interpret_chat import on, emit, SEND
from data_chat import KEYS, MESSAGES, STATES

async def _stream_request(provider, key, model, messages):
    url = f"{provider['base_url']}/chat/completions"
    headers = {"Authorization": f"Bearer {key['value']}", "Content-Type": "application/json"}
    body = {"model": model, "messages": messages, "stream": True}
    async with httpx.AsyncClient(timeout=120.0) as client:
        async with client.stream("POST", url, headers=headers, json=body) as r:
            ok = r.status_code == STATES["ok_status"]
            async for line in r.aiter_lines():
                if not ok:
                    break
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                try:
                    obj = json.loads(data)
                except Exception:
                    continue
                piece = obj.get("choices", [{}])[0].get("delta", {}).get("content", "")
                if piece:
                    SEND("chunk", {"text": piece})
            return {"ok": ok, "status": r.status_code}

def parse_blocks(text):
    blocks, buf, i = [], "", 0
    while i < len(text):
        if text.startswith("```", i):
            if buf.strip():
                blocks.append({"type": "text", "content": buf}); buf = ""
            j = text.find("\n", i + 3)
            lang = text[i + 3:j].strip() if j != -1 else ""
            end = text.find("```", j + 1) if j != -1 else -1
            if end == -1:
                buf += text[i:]; break
            body = text[j + 1:end]
            kind = "json" if lang.lower() == "json" or body.strip().startswith(("{", "[")) else "code"
            blocks.append({"type": kind, "lang": lang or "text", "content": body.rstrip("\n")})
            i = end + 3
        else:
            buf += text[i]; i += 1
    if buf.strip():
        blocks.append({"type": "text", "content": buf})
    return blocks

@on("request_ready")
async def handle_request(payload):
    provider = payload["provider"]
    key = next((k for k in KEYS if k["id"] == payload["key_id"]), None)
    SEND("status", {"kind": "stream", "state": "start"})
    result = await _stream_request(provider, key, payload["model"], payload["messages"])
    if not result["ok"]:
        emit("provider_fail", {"key_id": key["id"], "status": result["status"], "text": payload.get("text", "")})
        return
    emit("provider_ok", {"key_id": key["id"]})
    emit("stream_finished", {})

@on("save_assistant")
def handle_save(payload):
    raw = payload.get("text", "")
    MESSAGES.append({
        "id": payload.get("id", ""), "role": "assistant", "content": raw,
        "blocks": parse_blocks(raw), "ts": payload.get("ts", 0),
    })
    emit("message_saved", MESSAGES[-1])

@on("save_user")
def handle_save_user(payload):
    MESSAGES.append({
        "id": payload.get("id", ""), "role": "user", "content": payload.get("text", ""),
        "blocks": [{"type": "text", "content": payload.get("text", "")}],
        "ts": payload.get("ts", 0),
    })
    emit("message_saved", MESSAGES[-1])

# ================= ЗАГРУЗКА =================

import meta_chat