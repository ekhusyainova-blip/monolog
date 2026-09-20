# interpret_monolog.py — интерпретация AI Monolog
# Слой B. Шина, выбор провайдера/ключа/модели, merge метрик, extract_json,
# GitHub get/put, роут /chat. Условия — в A.

import json
import base64
import itertools
import re
from typing import Optional, List, Dict, Any

import httpx
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

from data_monolog import (
    PROVIDERS, MODEL_RULES, PROVIDER_ERRORS, PATHS, GITHUB_API,
    GITHUB_TOKEN, GITHUB_REPO, GITHUB_BRANCH, CODE_BRANCH,
    _DEV_KEYS_GROQ, ALLOW_BYOK, MANAGEMENT_KEY,
    MAX_MESSAGE_LEN, BASE_METRICS, safe_log, _safe_eq,
)

# ================= ШИНА =================

HANDLERS = {}
EVENTS = []
_dev_key_cycle = itertools.cycle(_DEV_KEYS_GROQ) if _DEV_KEYS_GROQ else None

def on(event):
    def deco(fn):
        HANDLERS.setdefault(event, []).append(fn)
        return fn
    return deco

def emit(event, payload=None):
    for fn in HANDLERS.get(event, []):
        fn(payload or {})

def SEND(event_type, data):
    EVENTS.append({"type": event_type, "data": data})

# ================= ВЫБОР ПРОВАЙДЕРА / КЛЮЧА / МОДЕЛИ =================

def next_dev_key() -> Optional[str]:
    if not _dev_key_cycle:
        return None
    return next(_dev_key_cycle)

def _tier_by_text(user_message, carried_metrics, models):
    text = (user_message or "").lower()
    heavy = any(kw in text for kw in MODEL_RULES["heavy_keywords"])
    long = len(user_message or "") > MODEL_RULES["long_message_threshold"]
    passport = (carried_metrics or {}).get("passport") or {}
    strategic = passport.get("level") in MODEL_RULES["strategic_levels"]
    tier = ("heavy" if heavy else
            "medium" if long or strategic else
            "light")
    return models.get(tier) or models.get("medium") or models.get("light")

def pick_provider_and_model(body, user_message, carried_metrics=None):
    provider = (body.get("provider") or "groq").strip().lower()
    provider = provider if provider in PROVIDERS else "groq"
    user_key = (body.get("api_key") or "").strip()
    dev_key = next_dev_key()
    if user_key and len(user_key) > 20 and ALLOW_BYOK:
        cfg = PROVIDERS[provider]
        return provider, cfg["base_url"], _tier_by_text(user_message, carried_metrics, cfg["models"]), user_key, "user"
    if dev_key:
        cfg = PROVIDERS["groq"]
        return "groq", cfg["base_url"], _tier_by_text(user_message, carried_metrics, cfg["models"]), dev_key, "developer"
    return None, None, None, None, "none"

# ================= РАЗБОР ОТВЕТА ИИ =================

def strip_thinking(text: str) -> str:
    if not text:
        return text
    text = re.sub(r" thinking.*? response", "", text, flags=re.DOTALL)
    text = re.sub(r"<reasoning>.*?</reasoning>", "", text, flags=re.DOTALL)
    return text.strip()

def extract_json(text: str) -> Optional[Dict[str, Any]]:
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
    depth, in_string, escape = 0, False, False
    for i in range(start, len(text)):
        ch = text[i]
        if escape:
            escape = False; continue
        if ch == "\\":
            escape = True; continue
        if ch == '"':
            in_string = not in_string; continue
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

# ================= COMPACT + MERGE МЕТРИК =================

def compact_carried(carried):
    if not carried:
        return {}
    out = {}
    p = carried.get("passport") or {}
    if p:
        out["passport"] = {"level": p.get("level"), "title": p.get("title"), "goal": p.get("goal")}
    pr = carried.get("profile") or {}
    if pr:
        out["profile"] = {"values": pr.get("values") or {}, "patterns": (pr.get("patterns") or [])[:5]}
    arts = carried.get("artifacts") or []
    if arts:
        compacted = []
        for a in arts[-3:]:
            if not isinstance(a, dict):
                continue
            item = {"id": a.get("id"), "name": a.get("name"), "type": a.get("type"),
                    "version": a.get("version"), "stage": a.get("stage")}
            content = a.get("content") or ""
            if content and len(content) < 6000:
                item["content"] = content
            compacted.append(item)
        out["artifacts"] = compacted
    return out

def merge_metrics(incoming, carried=None):
    carried = carried or {}
    result = {**BASE_METRICS, **carried}
    skip = ("passport", "profile", "reminder", "artifacts", "social_adaptation",
            "dominant_trait", "ideas", "dimension", "priority_drift", "mood_board")
    for k, v in (incoming or {}).items():
        if k in skip:
            continue
        if v is not None:
            result[k] = v

    inc_sa = (incoming or {}).get("social_adaptation")
    result["social_adaptation"] = ({"active": bool(inc_sa.get("active")),
                                    "reason": inc_sa.get("reason"),
                                    "level": inc_sa.get("level", "inactive")}
                                   if isinstance(inc_sa, dict)
                                   else carried.get("social_adaptation") or BASE_METRICS["social_adaptation"])

    inc_dt = (incoming or {}).get("dominant_trait")
    result["dominant_trait"] = ({"detected": bool(inc_dt.get("detected")),
                                 "influence": inc_dt.get("influence"),
                                 "risk": inc_dt.get("risk"),
                                 "stability_delta": float(inc_dt.get("stability_delta") or 0.0),
                                 "hint": inc_dt.get("hint"),
                                 "steps": list(inc_dt.get("steps") or []) if isinstance(inc_dt.get("steps"), list) else []}
                                if isinstance(inc_dt, dict)
                                else carried.get("dominant_trait") or BASE_METRICS["dominant_trait"])

    inc_ideas = (incoming or {}).get("ideas")
    if isinstance(inc_ideas, list):
        existing = list(carried.get("ideas") or [])
        seen = set(i.get("id") for i in existing if isinstance(i, dict))
        for it in inc_ideas:
            if isinstance(it, dict) and it.get("id") and it["id"] not in seen:
                existing.append(it); seen.add(it["id"])
        result["ideas"] = existing
    else:
        result["ideas"] = carried.get("ideas") or []

    result["dimension"] = (incoming or {}).get("dimension", carried.get("dimension"))
    result["priority_drift"] = (incoming or {}).get("priority_drift", carried.get("priority_drift"))
    result["mood_board"] = (incoming or {}).get("mood_board", carried.get("mood_board"))

    inc_pass = (incoming or {}).get("passport") or {}
    car_pass = carried.get("passport") or {}
    merged_pass = {**BASE_METRICS["passport"], **car_pass}
    for k, v in inc_pass.items():
        if k == "completion":
            if isinstance(v, (int, float)) and v > (merged_pass.get("completion") or 0):
                merged_pass["completion"] = int(v)
            continue
        if k in ("values", "constraints", "stakeholders", "risks", "metrics"):
            if isinstance(v, list) and v:
                merged_pass[k] = v
        else:
            if v not in (None, "", [], {}):
                merged_pass[k] = v
    result["passport"] = merged_pass

    inc_prof = (incoming or {}).get("profile") or {}
    car_prof = carried.get("profile") or {}
    merged_prof = {**BASE_METRICS["profile"], **car_prof}
    if isinstance(inc_prof.get("values"), dict) and inc_prof["values"]:
        merged_prof["values"] = {**merged_prof.get("values", {}), **inc_prof["values"]}
    for lk in ("patterns", "distortions", "insights", "skills"):
        old = list(merged_prof.get(lk) or [])
        new = inc_prof.get(lk) or []
        if isinstance(new, list):
            seen = set(map(str, old))
            for item in new:
                if str(item) not in seen:
                    old.append(str(item)); seen.add(str(item))
            merged_prof[lk] = old
    if isinstance(inc_prof.get("somatic"), dict):
        ms = {**(merged_prof.get("somatic") or {})}
        for k in ("energy", "tension", "focus"):
            v = inc_prof["somatic"].get(k)
            if isinstance(v, (int, float)):
                ms[k] = max(0.0, min(1.0, v))
        if inc_prof["somatic"].get("mood"):
            ms["mood"] = inc_prof["somatic"]["mood"]
        if inc_prof["somatic"].get("note"):
            ms["note"] = inc_prof["somatic"]["note"]
        merged_prof["somatic"] = ms
    result["profile"] = merged_prof

    inc_rem = (incoming or {}).get("reminder")
    result["reminder"] = inc_rem if inc_rem is not None else carried.get("reminder")

    inc_art = (incoming or {}).get("artifacts") or []
    car_art = list(carried.get("artifacts") or [])
    seen_ids = set(a.get("id") for a in car_art if isinstance(a, dict))
    for a in inc_art:
        if not isinstance(a, dict):
            continue
        aid = a.get("id")
        if aid and aid not in seen_ids:
            car_art.append(a); seen_ids.add(aid)
    result["artifacts"] = car_art
    return result

# ================= GITHUB =================

async def github_get_json(path: str):
    url = f"{GITHUB_API}/repos/{GITHUB_REPO}/contents/{path}"
    headers = {"Accept": "application/vnd.github+json"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get(url, headers=headers, params={"ref": GITHUB_BRANCH})
        if r.status_code == 404:
            return None, None
        if r.status_code >= 400:
            raise HTTPException(status_code=502, detail=f"Не удалось прочитать {path}")
        data = r.json()
        try:
            raw = base64.b64decode(data.get("content", "")).decode("utf-8")
            parsed = json.loads(raw) if raw.strip() else None
        except Exception:
            parsed = None
        return parsed, data.get("sha")

async def github_put_json(path: str, content_obj, message: str):
    if not GITHUB_TOKEN:
        raise HTTPException(status_code=503, detail="GITHUB_TOKEN не настроен")
    _, sha = await github_get_json(path)
    content = json.dumps(content_obj, ensure_ascii=False, indent=2)
    content_b64 = base64.b64encode(content.encode("utf-8")).decode("utf-8")
    url = f"{GITHUB_API}/repos/{GITHUB_REPO}/contents/{path}"
    headers = {"Accept": "application/vnd.github+json", "Authorization": f"Bearer {GITHUB_TOKEN}"}
    body = {"message": message, "content": content_b64, "branch": GITHUB_BRANCH}
    if sha:
        body["sha"] = sha
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.put(url, headers=headers, json=body)
        if r.status_code >= 400:
            raise HTTPException(status_code=502, detail=f"Не удалось сохранить {path}")
        return True

# ================= ОБРАБОТЧИКИ ЧАТА =================

@on("chat_request")
def handle_chat_request(payload):
    body = payload.get("body") or {}
    request = payload.get("request")
    user_message = (body.get("message") or "").strip()
    attachments = body.get("attachments") or []
    carried_metrics = body.get("carried_metrics") or {}

    if not user_message and not attachments:
        SEND("chat_error", {"status": 400, "detail": "Пустое сообщение"})
        return
    if len(user_message) > MAX_MESSAGE_LEN:
        user_message = user_message[:MAX_MESSAGE_LEN]
    if not isinstance(attachments, list):
        attachments = []
    if not isinstance(carried_metrics, dict):
        carried_metrics = {}

    provider, base_url, model, api_key, source = pick_provider_and_model(body, user_message, carried_metrics)
    if not api_key:
        SEND("chat_error", {"status": 503, "detail": "Нет доступных ключей. Введите свой ключ в настройках → Ключ API."})
        return

    management_mode = _safe_eq((body.get("management_key") or "").strip(), MANAGEMENT_KEY)
    safe_log(f"Chat | provider={provider} | source={source} | model={model} | management={management_mode} | len={len(user_message)}")

    emit("call_meta", {
        "user_message": user_message,
        "carried_metrics": carried_metrics,
        "api_key": api_key, "base_url": base_url, "model": model, "provider": provider,
        "management_mode": management_mode, "attachments": attachments, "source": source,
    })

@on("meta_ready")
def on_meta_ready(payload):
    full_metrics = merge_metrics(payload.get("meta_delta") or {}, payload.get("carried_metrics") or {})
    full_metrics["management_mode"] = payload.get("management_mode", False)
    emit("call_content", {**payload, "full_metrics": full_metrics})

@on("content_ready")
def on_content_ready(payload):
    parsed = payload.get("parsed") or {}
    reply_text = parsed.get("reply_text", "")
    full_metrics = payload.get("full_metrics") or {}
    if not reply_text:
        reply_text = "Не получилось построить ответ. Попробуйте переформулировать запрос."
        full_metrics["protocol_integrity"] = False
        full_metrics["indicator_status"] = "warning"
    SEND("chat_done", {
        "reply_text": reply_text,
        "metrics": full_metrics,
        "meta_delta": payload.get("meta_delta") or {},
        "key_source": payload.get("source", ""),
        "provider_used": payload.get("provider", ""),
        "model_used": payload.get("model", ""),
        "management_mode": payload.get("management_mode", False),
    })

@on("provider_error")
def on_provider_error(payload):
    status = payload.get("status")
    name = payload.get("provider_name", payload.get("provider", ""))
    template = PROVIDER_ERRORS.get(status)
    detail = (template.format(name=name, retry=payload.get("retry_after", "?"))
              if template else f"Ошибка {name} API.")
    if payload.get("context") == "chat":
        SEND("chat_error", {"status": status, "detail": detail})
    else:
        emit("raise_http", {"status": status, "detail": detail})

# ================= ЗАГРУЗКА СЛОЁВ =================

import solve_monolog