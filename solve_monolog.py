# solve_monolog.py — решение AI Monolog
# Слой C. Вызовы провайдера (meta + content), обработка ошибок.
# Условия — в A. Здесь только события.

import json
import time
import httpx
from fastapi import HTTPException

from interpret_monolog import (
    on, emit, SEND, extract_json, compact_carried,
    github_get_json, github_put_json,
)
from data_monolog import (
    PROVIDERS, PATHS, TIMEOUT, MAX_TOKENS, META_MAX_TOKENS,
    LAYER_A, LAYER_B, LAYER_A_CONTENT,
    MAX_ATTACHMENTS, MAX_ATTACH_LEN, safe_log,
)

# ================= ВЫЗОВ ПРОВАЙДЕРА =================

@on("call_meta")
async def on_call_meta(payload):
    await _call_meta(payload)

@on("call_content")
async def on_call_content(payload):
    await _call_content(payload)

async def _call_provider(messages, api_key, base_url, model, provider, max_tokens):
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    if provider == "openrouter":
        headers["HTTP-Referer"] = "https://monolog.onrender.com"
        headers["X-Title"] = "AI Monolog"
    payload = {"model": model, "messages": messages, "max_tokens": max_tokens, "temperature": 0.6}
    cfg = PROVIDERS.get(provider, {})
    if cfg.get("reasoning_effort"):
        if model.startswith("openai/gpt-oss") or model.startswith("gpt-oss"):
            payload["reasoning_effort"] = "low"
        elif model.startswith("qwen"):
            payload["reasoning_effort"] = "none"
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        r = await client.post(base_url, headers=headers, json=payload)
        remaining = r.headers.get("x-ratelimit-remaining-tokens", "?")
        safe_log(f"Provider [{provider}/{model}] status={r.status_code} remaining={remaining}")
        if r.status_code >= 400:
            emit("provider_error", {
                "status": r.status_code, "provider": provider,
                "provider_name": cfg.get("name", provider),
                "retry_after": r.headers.get("retry-after"), "context": "chat",
            })
            return None
        data = r.json()
        return strip_thinking(data["choices"][0]["message"]["content"])

def strip_thinking(text: str) -> str:
    import re
    if not text:
        return text
    text = re.sub(r" thinking.*? response", "", text, flags=re.DOTALL)
    text = re.sub(r"<reasoning>.*?</reasoning>", "", text, flags=re.DOTALL)
    return text.strip()

async def _call_meta(payload):
    if not LAYER_B:
        emit("meta_ready", {**payload, "meta_delta": {}})
        return
    messages = [{"role": "system", "content": LAYER_B}]
    meta_payload = {"prev": compact_carried(payload.get("carried_metrics") or {}),
                    "msg": (payload.get("user_message") or "")[:200]}
    messages.append({"role": "user", "content": json.dumps(meta_payload, ensure_ascii=False)})
    raw = await _call_provider(messages, payload["api_key"], payload["base_url"],
                               payload["model"], payload["provider"], META_MAX_TOKENS)
    if raw is None:
        return
    meta_delta = extract_json(raw) or {}
    emit("meta_ready", {**payload, "meta_delta": meta_delta})

async def _call_content(payload):
    system = LAYER_A + "\n\n" + LAYER_A_CONTENT
    user_content = payload.get("user_message") or "Проанализируй вложения."
    attachments = payload.get("attachments") or []
    if attachments:
        block = "\n\n=== ВЛОЖЕНИЯ ===\n"
        for a in attachments[:MAX_ATTACHMENTS]:
            txt = (a.get("text") or "")[:MAX_ATTACH_LEN]
            block += f"\n[Файл: {a.get('name', 'без имени')}]\n{txt}\n"
        user_content += block
    user_content += "\n\n=== СОСТОЯНИЕ ===\n" + json.dumps(compact_carried(payload.get("full_metrics") or {}), ensure_ascii=False)
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user_content},
    ]
    raw = await _call_provider(messages, payload["api_key"], payload["base_url"],
                               payload["model"], payload["provider"], MAX_TOKENS)
    if raw is None:
        return
    parsed = extract_json(raw) or {}
    if "reply_text" not in parsed:
        parsed = {"reply_text": raw}
    emit("content_ready", {**payload, "parsed": parsed})

# ================= ПУБЛИЧНЫЙ СЛОЙ =================

@on("github_get")
async def on_github_get(payload):
    data, sha = await github_get_json(payload["path"])
    SEND(payload["reply_event"], {"data": data, "sha": sha, "path": payload["path"]})

@on("github_put")
async def on_github_put(payload):
    ok = await github_put_json(payload["path"], payload["content"], payload["message"])
    SEND(payload["reply_event"], {"ok": ok, "path": payload["path"]})

# ================= ЗАГРУЗКА =================

import meta_monolog