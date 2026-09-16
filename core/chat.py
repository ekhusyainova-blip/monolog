# core/chat.py — основной диалог и служебные эндпоинты ядра.
# /chat — единственный вход к провайдеру. /health и /providers — диагностика.

import json
import re
import logging

import httpx
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse

from core.prompts import LAYER_A, LAYER_B, LAYER_A_CONTENT
from core.providers import (
    PROVIDERS, MAX_TOKENS, META_MAX_TOKENS, TIMEOUT,
    MAX_MESSAGE_LEN, SOFT_MESSAGE_LEN, MAX_ATTACH_LEN, MAX_ATTACHMENTS,
    ALLOW_BYOK, MANAGEMENT_KEY, _DEV_KEYS_GROQ,
    pick_provider_and_model, safe_eq,
)
from core.metrics import BASE_METRICS, compact_carried, merge_metrics

log = logging.getLogger("monolog")
SECRET_PATTERN = re.compile(r"(sk_[A-Za-z0-9_\-]{8,}|gsk_[A-Za-z0-9_\-]{8,}|Bearer\s+[A-Za-z0-9_\-\.]{10,})")

def safe_log(msg: str):
    log.info(SECRET_PATTERN.sub("[SECRET]", str(msg)))


def strip_thinking(text: str) -> str:
    if not text:
        return text
    text = re.sub(r" thinking.*?", "", text, flags=re.DOTALL)
    text = re.sub(r"<reasoning>.*?</reasoning>", "", text, flags=re.DOTALL)
    return text.strip()


def extract_json(text):
    if not text:
        return None
    text = text.replace("\ufeff", "").replace("\u200b", "").replace("\u200c", "").replace("\u200d", "")
    text = strip_thinking(text)
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```\s*$", "", text)
    start = text.find("{")
    if start == -1:
        return None
    try:
        return json.loads(text[start:])
    except Exception:
        pass
    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(text)):
        ch = text[i]
        if escape:
            escape = False
            continue
        if ch == "\\":
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                chunk = text[start:i + 1]
                try:
                    return json.loads(chunk)
                except Exception:
                    fixed = re.sub(r"(?<!\\)\n", "\\\\n", chunk)
                    try:
                        return json.loads(fixed)
                    except Exception:
                        return None
    return None


async def call_provider(messages, api_key, base_url, model, provider, max_tokens=MAX_TOKENS):
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    if provider == "openrouter":
        headers["HTTP-Referer"] = "https://monolog.onrender.com"
        headers["X-Title"] = "AI Monolog"
    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": 0.6,
    }
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
        if r.status_code == 429:
            retry_after = r.headers.get("retry-after")
            detail = (f"Лимит вашего ключа исчерпан. Повторите через {retry_after} сек."
                      if retry_after else
                      "Лимит ключа исчерпан. Он обновится автоматически. Или введите свой ключ в настройках → Ключ API.")
            raise HTTPException(status_code=429, detail=detail)
        if r.status_code == 402:
            raise HTTPException(status_code=402, detail="На провайдере закончились кредиты. Пополните баланс или смените провайдера.")
        if r.status_code in (401, 403):
            raise HTTPException(status_code=403, detail="Ключ не принят провайдером. Проверьте ключ в настройках → Ключ API.")
        if r.status_code == 413:
            raise HTTPException(status_code=413, detail="Запрос слишком длинный. Сократите или прикрепите файл.")
        if r.status_code >= 500:
            log.error(f"Provider error {r.status_code}")
            raise HTTPException(status_code=502, detail=f"{PROVIDERS.get(provider, {}).get('name', provider)} недоступен. Попробуйте позже.")
        if r.status_code >= 400:
            log.error(f"Provider error {r.status_code}")
            raise HTTPException(status_code=r.status_code, detail=f"Ошибка {PROVIDERS.get(provider, {}).get('name', provider)} API.")
        data = r.json()
        return strip_thinking(data["choices"][0]["message"]["content"])


async def call_meta(user_message, carried_metrics, api_key, base_url, model, provider):
    if not LAYER_B:
        return {}
    messages = [{"role": "system", "content": LAYER_B}]
    payload = {"prev": compact_carried(carried_metrics), "msg": (user_message or "")[:200]}
    messages.append({"role": "user", "content": json.dumps(payload, ensure_ascii=False)})
    try:
        raw = await call_provider(messages, api_key, base_url, model, provider, max_tokens=META_MAX_TOKENS)
        return extract_json(raw) or {}
    except HTTPException:
        raise
    except Exception as e:
        safe_log(f"meta failed: {e}")
        return {}


async def call_content(user_message, full_metrics, api_key, base_url, model, provider, attachments=None):
    system = LAYER_A + "\n\n" + LAYER_A_CONTENT
    user_content = user_message or "Проанализируй вложения."
    if attachments:
        block = "\n\n=== ВЛОЖЕНИЯ ===\n"
        for a in attachments[:MAX_ATTACHMENTS]:
            txt = (a.get("text") or "")[:MAX_ATTACH_LEN]
            block += f"\n[Файл: {a.get('name', 'без имени')}]\n{txt}\n"
        user_content += block
    user_content += "\n\n=== СОСТОЯНИЕ ===\n" + json.dumps(compact_carried(full_metrics), ensure_ascii=False)
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user_content},
    ]
    raw = await call_provider(messages, api_key, base_url, model, provider, max_tokens=MAX_TOKENS)
    parsed = extract_json(raw) or {}
    if "reply_text" not in parsed:
        parsed = {"reply_text": raw}
    return parsed


router = APIRouter()


@router.get("/health")
async def health():
    return {
        "status": "ok",
        "version": "2.1",
        "dev_keys": len(_DEV_KEYS_GROQ),
        "byok": ALLOW_BYOK,
        "management_key_set": bool(MANAGEMENT_KEY),
        "providers": list(PROVIDERS.keys()),
        "prompts_loaded": {
            "layer_a": bool(LAYER_A),
            "layer_b": bool(LAYER_B),
            "layer_a_content": bool(LAYER_A_CONTENT),
        },
        "limits": {
            "max_message_len": MAX_MESSAGE_LEN,
            "soft_message_len": SOFT_MESSAGE_LEN,
            "max_tokens": MAX_TOKENS,
            "meta_max_tokens": META_MAX_TOKENS,
        },
    }


@router.get("/providers")
async def providers_info():
    out = []
    urls = {
        "groq": "https://console.groq.com/keys",
        "openrouter": "https://openrouter.ai/keys",
        "cerebras": "https://cloud.cerebras.ai",
        "sambanova": "https://cloud.sambanova.ai",
    }
    for pid, cfg in PROVIDERS.items():
        out.append({
            "id": pid,
            "name": cfg["name"],
            "url": urls.get(pid, ""),
            "models": list(cfg.get("all_models") or []),
        })
    return JSONResponse({"providers": out})


@router.post("/chat")
async def chat(request: Request):
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Некорректный формат запроса")

    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="Тело запроса должно быть объектом")

    user_message = (body.get("message") or "").strip()
    attachments = body.get("attachments") or []
    carried_metrics = body.get("carried_metrics") or {}

    if not user_message and not attachments:
        raise HTTPException(status_code=400, detail="Пустое сообщение")

    if len(user_message) > MAX_MESSAGE_LEN:
        user_message = user_message[:MAX_MESSAGE_LEN]

    if not isinstance(attachments, list):
        attachments = []
    if not isinstance(carried_metrics, dict):
        carried_metrics = {}

    provider, base_url, model, api_key, source = pick_provider_and_model(body, user_message, carried_metrics)
    if not api_key:
        raise HTTPException(status_code=503, detail="Нет доступных ключей. Введите свой ключ в настройках → Ключ API.")

    management_mode = safe_eq((body.get("management_key") or "").strip(), MANAGEMENT_KEY)
    safe_log(f"Chat | provider={provider} | source={source} | model={model} | management={management_mode} | len={len(user_message)}")

    try:
        meta_delta = await call_meta(user_message, carried_metrics, api_key, base_url, model, provider)
        full_metrics = merge_metrics(meta_delta, carried_metrics)
        full_metrics["management_mode"] = management_mode

        content_result = await call_content(user_message, full_metrics, api_key, base_url, model, provider, attachments)
        reply_text = content_result.get("reply_text", "")
        if not reply_text:
            reply_text = "Не получилось построить ответ. Попробуйте переформулировать запрос."
            full_metrics["protocol_integrity"] = False
            full_metrics["indicator_status"] = "warning"

        return JSONResponse({
            "reply_text": reply_text,
            "metrics": full_metrics,
            "meta_delta": meta_delta,
            "key_source": source,
            "provider_used": provider,
            "model_used": model,
            "management_mode": management_mode,
        })
    except HTTPException:
        raise
    except Exception as e:
        safe_log(f"Chat error: {e}")
        fallback_metrics = merge_metrics({}, carried_metrics)
        fallback_metrics["protocol_integrity"] = False
        fallback_metrics["indicator_status"] = "warning"
        fallback_metrics["management_mode"] = management_mode
        return JSONResponse({
            "reply_text": "Внутренняя ошибка сервера. Мы уже работаем над этим. Попробуйте ещё раз.",
            "metrics": fallback_metrics,
            "key_source": source,
            "provider_used": provider,
            "model_used": model,
            "management_mode": management_mode,
        })