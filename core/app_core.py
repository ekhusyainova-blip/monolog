# core/app_core.py — ядро Monolog.
# Провайдеры, промпты, /chat, /health, /providers.
# Меняется вручную, редко. Это смысловой центр кода.

import os
import re
import json
import hmac
import logging
import itertools
from typing import Optional, List, Dict, Any

import httpx
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse
from dotenv import load_dotenv

load_dotenv()

log = logging.getLogger("monolog")
SECRET_PATTERN = re.compile(r"(sk_[A-Za-z0-9_\-]{8,}|gsk_[A-Za-z0-9_\-]{8,}|Bearer\s+[A-Za-z0-9_\-\.]{10,})")

def safe_log(msg: str):
    log.info(SECRET_PATTERN.sub("[SECRET]", str(msg)))


PROVIDERS = {
    "groq": {
        "name": "Groq",
        "base_url": "https://api.groq.com/openai/v1/chat/completions",
        "models": {
            "light": "openai/gpt-oss-20b",
            "medium": "openai/gpt-oss-120b",
            "heavy": "qwen/qwen3.6-27b",
        },
        "all_models": [
            "openai/gpt-oss-20b",
            "openai/gpt-oss-120b",
            "qwen/qwen3.6-27b",
            "llama-3.3-70b-versatile",
            "llama-3.1-8b-instant",
        ],
        "reasoning_effort": True,
    },
    "openrouter": {
        "name": "OpenRouter",
        "base_url": "https://openrouter.ai/api/v1/chat/completions",
        "models": {
            "light": "openai/gpt-oss-20b:free",
            "medium": "openai/gpt-oss-120b:free",
            "heavy": "qwen/qwen-coder:free",
        },
        "all_models": [
            "openai/gpt-oss-20b:free",
            "openai/gpt-oss-120b:free",
            "qwen/qwen-coder:free",
            "meta-llama/llama-3.3-70b-instruct:free",
            "google/gemma-2-9b-it:free",
        ],
        "reasoning_effort": False,
    },
    "cerebras": {
        "name": "Cerebras",
        "base_url": "https://api.cerebras.ai/v1/chat/completions",
        "models": {
            "light": "gpt-oss-20b",
            "medium": "gpt-oss-120b",
            "heavy": "gpt-oss-120b",
        },
        "all_models": ["gpt-oss-20b", "gpt-oss-120b", "llama3.1-8b", "llama3.1-70b"],
        "reasoning_effort": True,
    },
    "sambanova": {
        "name": "SambaNova",
        "base_url": "https://api.sambanova.ai/v1/chat/completions",
        "models": {
            "light": "Meta-Llama-3.3-70B-Instruct",
            "medium": "Meta-Llama-3.3-70B-Instruct",
            "heavy": "DeepSeek-V3.1",
        },
        "all_models": [
            "Meta-Llama-3.3-70B-Instruct",
            "Meta-Llama-3.1-8B-Instruct",
            "DeepSeek-V3.1",
        ],
        "reasoning_effort": False,
    },
}

MAX_TOKENS = 3500
META_MAX_TOKENS = 800
TIMEOUT = 120.0

MAX_MESSAGE_LEN = 8000
SOFT_MESSAGE_LEN = 4000
MAX_ATTACH_LEN = 3000
MAX_ATTACHMENTS = 3

_DEV_KEYS_GROQ: List[str] = [
    k.strip() for k in os.getenv("GROQ_API_KEYS", "").split(",") if k.strip()
]
_dev_key_cycle = itertools.cycle(_DEV_KEYS_GROQ) if _DEV_KEYS_GROQ else None

ALLOW_BYOK = os.getenv("ALLOW_BYOK", "true").lower() == "true"
MANAGEMENT_KEY = os.getenv("MANAGEMENT_KEY", "").strip()


def _load(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip()
    except FileNotFoundError:
        log.warning(f"Prompt file not found: {path}")
        return ""


LAYER_A = _load("prompts/layer_a.txt")
LAYER_B = _load("prompts/layer_b.txt")
LAYER_A_CONTENT = _load("prompts/layer_a_content_prompt")


BASE_METRICS = {
    "stability_index": 0.0,
    "indicator_status": "success",
    "cycles_completed": 0,
    "lots_balance": "+0.0",
    "index_delta": None,
    "mind_scale": "micro",
    "human_contribution": 0.0,
    "cognitive_pulse": "stable",
    "mode_suggested": "analyst",
    "layer_marker": None,
    "ai_note": None,
    "learning_template": None,
    "reset_proposal": None,
    "reminder": None,
    "value_choices": [],
    "risk_intercept": None,
    "social_adaptation": {"active": False, "reason": None, "level": "inactive"},
    "dominant_trait": {"detected": False, "influence": None, "risk": None,
                       "stability_delta": 0.0, "hint": None, "steps": []},
    "passport": {
        "level": "micro", "title": None, "goal": None, "result": None,
        "mission": None, "values": [], "constraints": [], "stakeholders": [],
        "risks": [], "metrics": [], "completion": 0,
    },
    "profile": {
        "values": {}, "patterns": [], "distortions": [], "insights": [],
        "somatic": {"energy": 0.5, "tension": 0.3, "focus": 0.5,
                    "mood": None, "note": None},
        "skills": [],
    },
    "dimension": None,
    "priority_drift": None,
    "mood_board": None,
    "ideas": [],
    "artifacts": [],
    "protocol_integrity": True,
    "management_mode": False,
    "public_index": {"given": 0, "taken": 0, "help_score": 0, "reputation": 0},
}


def next_dev_key() -> Optional[str]:
    if not _dev_key_cycle:
        return None
    return next(_dev_key_cycle)


def _safe_eq(a: str, b: str) -> bool:
    if not a or not b:
        return False
    return hmac.compare_digest(a, b)


def _pick_model_tier(user_message, carried_metrics, models):
    text = (user_message or "").lower()
    heavy_keywords = [
        "статья", "лонгрид", "пост", "напиши",
        "проанализируй", "анализ", "план", "стратег",
        "архитектур", "спроектируй", "разработай",
        "документ", "тз", "отчёт", "отчет",
    ]
    if any(kw in text for kw in heavy_keywords):
        return models.get("heavy") or models.get("medium") or models.get("light")
    if len(user_message or "") > 200:
        return models.get("medium") or models.get("light")
    if carried_metrics:
        passport = carried_metrics.get("passport") or {}
        if passport.get("level") in ("strategic", "systemic"):
            return models.get("medium") or models.get("light")
    return models.get("light") or models.get("medium")


def pick_provider_and_model(body, user_message, carried_metrics=None):
    provider = (body.get("provider") or "groq").strip().lower()
    if provider not in PROVIDERS:
        provider = "groq"
    user_key = (body.get("api_key") or "").strip()
    if user_key and len(user_key) > 20:
        cfg = PROVIDERS[provider]
        model = _pick_model_tier(user_message, carried_metrics, cfg["models"])
        return provider, cfg["base_url"], model, user_key, "user"
    dev_key = next_dev_key()
    if dev_key:
        cfg = PROVIDERS["groq"]
        model = _pick_model_tier(user_message, carried_metrics, cfg["models"])
        return "groq", cfg["base_url"], model, dev_key, "developer"
    return None, None, None, None, "none"


def strip_thinking(text: str) -> str:
    if not text:
        return text
    text = re.sub(r" thinking.*?", "", text, flags=re.DOTALL)
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


def compact_carried(carried):
    if not carried:
        return {}
    out = {}
    p = carried.get("passport") or {}
    if p:
        out["passport"] = {"level": p.get("level"), "title": p.get("title"), "goal": p.get("goal")}
    pr = carried.get("profile") or {}
    if pr:
        out["profile"] = {
            "values": pr.get("values") or {},
            "patterns": (pr.get("patterns") or [])[:5],
        }
    arts = carried.get("artifacts") or []
    if arts:
        compacted = []
        for a in arts[-3:]:
            if not isinstance(a, dict):
                continue
            item = {
                "id": a.get("id"), "name": a.get("name"), "type": a.get("type"),
                "version": a.get("version"), "stage": a.get("stage"),
            }
            content = a.get("content") or ""
            if content and len(content) < 6000:
                item["content"] = content
            compacted.append(item)
        out["artifacts"] = compacted
    return out


def merge_metrics(incoming, carried=None):
    carried = carried or {}
    result = {**BASE_METRICS, **carried}
    skip_keys = ("passport", "profile", "reminder", "artifacts", "social_adaptation",
                 "dominant_trait", "ideas", "dimension", "priority_drift", "mood_board")
    for k, v in (incoming or {}).items():
        if k in skip_keys:
            continue
        if v is not None:
            result[k] = v

    inc_sa = (incoming or {}).get("social_adaptation")
    if isinstance(inc_sa, dict):
        result["social_adaptation"] = {
            "active": bool(inc_sa.get("active")),
            "reason": inc_sa.get("reason"),
            "level": inc_sa.get("level", "inactive"),
        }
    else:
        result["social_adaptation"] = carried.get("social_adaptation") or BASE_METRICS["social_adaptation"]

    inc_dt = (incoming or {}).get("dominant_trait")
    if isinstance(inc_dt, dict):
        result["dominant_trait"] = {
            "detected": bool(inc_dt.get("detected")),
            "influence": inc_dt.get("influence"),
            "risk": inc_dt.get("risk"),
            "stability_delta": float(inc_dt.get("stability_delta") or 0.0),
            "hint": inc_dt.get("hint"),
            "steps": list(inc_dt.get("steps") or []) if isinstance(inc_dt.get("steps"), list) else [],
        }
    else:
        result["dominant_trait"] = carried.get("dominant_trait") or BASE_METRICS["dominant_trait"]

    inc_ideas = (incoming or {}).get("ideas")
    if isinstance(inc_ideas, list):
        existing = list(carried.get("ideas") or [])
        seen = set(i.get("id") for i in existing if isinstance(i, dict))
        for it in inc_ideas:
            if isinstance(it, dict) and it.get("id") and it["id"] not in seen:
                existing.append(it)
                seen.add(it["id"])
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
    for list_key in ("patterns", "distortions", "insights", "skills"):
        old = list(merged_prof.get(list_key) or [])
        new = inc_prof.get(list_key) or []
        if isinstance(new, list):
            seen = set(map(str, old))
            for item in new:
                if str(item) not in seen:
                    old.append(str(item))
                    seen.add(str(item))
            merged_prof[list_key] = old
    if isinstance(inc_prof.get("somatic"), dict):
        merged_som = {**(merged_prof.get("somatic") or {})}
        for k in ("energy", "tension", "focus"):
            v = inc_prof["somatic"].get(k)
            if isinstance(v, (int, float)):
                merged_som[k] = max(0.0, min(1.0, v))
        if inc_prof["somatic"].get("mood"):
            merged_som["mood"] = inc_prof["somatic"]["mood"]
        if inc_prof["somatic"].get("note"):
            merged_som["note"] = inc_prof["somatic"]["note"]
        merged_prof["somatic"] = merged_som
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
            car_art.append(a)
            seen_ids.add(aid)
    result["artifacts"] = car_art

    return result


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


# --- router ---
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

    management_mode = _safe_eq((body.get("management_key") or "").strip(), MANAGEMENT_KEY)
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