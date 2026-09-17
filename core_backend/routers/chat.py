# core_backend/routers/chat.py
# Эндпоинт /chat. APIRouter — подключается в app.py автоматически.

import json
import hmac
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse

from core_backend.config import (
    LAYER_A,
    LAYER_B,
    LAYER_A_CONTENT,
    MAX_TOKENS,
    META_MAX_TOKENS,
    MAX_MESSAGE_LEN,
    MAX_ATTACHMENTS,
    MAX_ATTACH_LEN,
    MANAGEMENT_KEY,
    safe_log,
)
from core_backend.metrics import BASE_METRICS, merge_metrics, compact_carried
from core_backend.providers import pick_provider_and_model, extract_json
from core_backend.provider_rotation import call_with_fallback


router = APIRouter()


def _safe_eq(a: str, b: str) -> bool:
    if not a or not b:
        return False
    return hmac.compare_digest(a, b)


async def call_meta(user_message, carried_metrics, api_key, base_url, model, provider):
    if not LAYER_B:
        return {}
    messages = [{"role": "system", "content": LAYER_B}]
    payload = {
        "prev": compact_carried(carried_metrics),
        "msg": (user_message or "")[:200],
    }
    messages.append({"role": "user", "content": json.dumps(payload, ensure_ascii=False)})
    try:
        result = await call_with_fallback(
            messages,
            user_api_key=api_key,
            user_provider=provider,
            user_model=model,
            max_tokens=META_MAX_TOKENS,
        )
        return extract_json(result["text"]) or {}
    except HTTPException:
        raise
    except Exception as e:
        safe_log(f"meta failed: {e}")
        return {}


async def call_content(user_message, full_metrics, api_key, base_url, model, provider, attachments=None):
    system = (LAYER_A + "\n\n" + LAYER_A_CONTENT).strip()
    user_content = user_message or "Проанализируй вложения."
    if attachments:
        block = "\n\n=== ВЛОЖЕНИЯ ===\n"
        for a in attachments[:MAX_ATTACHMENTS]:
            txt = (a.get("text") or "")[:MAX_ATTACH_LEN]
            block += f"\n[Файл: {a.get('name', 'без имени')}]\n{txt}\n"
        user_content += block
    user_content += "\n\n=== СОСТОЯНИЕ ===\n" + json.dumps(compact_carried(full_metrics), ensure_ascii=False)
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": user_content})

    result = await call_with_fallback(
        messages,
        user_api_key=api_key,
        user_provider=provider,
        user_model=model,
        max_tokens=MAX_TOKENS,
    )
    raw = result["text"]
    parsed = extract_json(raw) or {}
    if "reply_text" not in parsed:
        parsed = {"reply_text": raw}
    return parsed


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

    provider, base_url, model, api_key, source = pick_provider_and_model(
        body, user_message, carried_metrics
    )
    if not api_key:
        raise HTTPException(status_code=503, detail="Нет доступных ключей.")

    management_mode = _safe_eq((body.get("management_key") or "").strip(), MANAGEMENT_KEY)
    safe_log(f"Chat | provider={provider} | source={source} | model={model} | management={management_mode}")

    try:
        meta_delta = await call_meta(
            user_message, carried_metrics, api_key, base_url, model, provider
        )
        full_metrics = merge_metrics(meta_delta, carried_metrics)
        full_metrics["management_mode"] = management_mode

        content_result = await call_content(
            user_message, full_metrics, api_key, base_url, model, provider, attachments
        )
        reply_text = content_result.get("reply_text", "")
        if not reply_text:
            reply_text = "Не получилось построить ответ."
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
            "reply_text": "Внутренняя ошибка. Попробуйте ещё раз.",
            "metrics": fallback_metrics,
            "key_source": source,
            "provider_used": provider,
            "model_used": model,
            "management_mode": management_mode,
        })