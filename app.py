# app.py
# Monolog — stateless-прокси к 4 провайдерам LLM + блог + Word-экспорт.
# Ключи: BLOG_KEY (блог + расширенные метрики), MANAGEMENT_KEY (Управление + всё).
# Пакет разработчика: /code/* (в ветку dev).
# Слой B достраивается, но подгружается в системный промпт.
# История НЕ отправляется целиком — только сжатый контекст.

import os
import re
import json
import time
import base64
import logging
import itertools
from io import BytesIO
from typing import Optional, List, Dict, Any

import httpx
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("monolog")

PROVIDERS = {
    "groq": {
        "name": "Groq",
        "base_url": "https://api.groq.com/openai/v1/chat/completions",
        "models": {
            "light": "openai/gpt-oss-20b",
            "medium": "openai/gpt-oss-120b",
            "heavy": "qwen/qwen3.6-27b",
        },
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
        "reasoning_effort": False,
    },
}

MAX_TOKENS = 6000
TIMEOUT = 120.0

_DEV_KEYS_GROQ: List[str] = [k.strip() for k in os.getenv("GROQ_API_KEYS", "").split(",") if k.strip()]
_dev_key_cycle = itertools.cycle(_DEV_KEYS_GROQ) if _DEV_KEYS_GROQ else None
ALLOW_BYOK = os.getenv("ALLOW_BYOK", "true").lower() == "true"

# ИЗМЕНЕНО: разведение ключей
BLOG_KEY = "Эгида-Эльвира-7"                                   # константа — блог + расширенные метрики
MANAGEMENT_KEY = os.getenv("MANAGEMENT_KEY", "").strip()       # из Render — Управление + всё
AUTHOR_SECRET = os.getenv("AUTHOR_SECRET", BLOG_KEY).strip()   # алиас BLOG_KEY (совместимость)

# GitHub
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "").strip()
GITHUB_REPO = os.getenv("GITHUB_REPO", "ekhusyainova-blip/monolog").strip()
GITHUB_BRANCH = os.getenv("GITHUB_BRANCH", "main").strip()
BLOG_PATH = "blog/posts.json"

# Пакет разработчика — ветка dev
CODE_BRANCH = "dev"

# Папки промптов и схем
PROMPTS_DIR = "prompts"
SCHEMAS_DIR = "schemas"


def _load(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip()
    except FileNotFoundError:
        log.warning(f"File not found: {path}")
        return ""


# НОВОЕ: загрузка слоёв и схем
LAYER_A = _load(f"{PROMPTS_DIR}/layer_a_level1.txt") or _load("layer_a.txt") or _load("layer_a.md")
LAYER_B = _load(f"{PROMPTS_DIR}/layer_b_level1.txt") or _load("layer_b.txt") or _load("layer_b.md")

def _load_schema(name: str) -> Dict[str, Any]:
    path = f"{SCHEMAS_DIR}/{name}.json"
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        log.warning(f"Schema not found: {path}")
        return {}
    except json.JSONDecodeError as e:
        log.warning(f"Schema invalid JSON: {path}: {e}")
        return {}

SCHEMAS = {
    "metrics": _load_schema("metrics"),
    "trust": _load_schema("trust"),
    "artifacts": _load_schema("artifacts"),
    "management": _load_schema("management"),
    "keys": _load_schema("keys"),
}


def mask_key(key: str) -> str:
    if not key or len(key) < 12:
        return "***"
    return f"{key[:6]}...{key[-4:]}"


def next_dev_key() -> Optional[str]:
    if not _dev_key_cycle:
        return None
    return next(_dev_key_cycle)


# ИЗМЕНЕНО: проверки ключей
def get_request_keys(request: Request) -> Dict[str, str]:
    """Собирает ключи из заголовков."""
    return {
        "author": request.headers.get("X-Author-Key", "").strip(),
        "management": request.headers.get("X-Management-Key", "").strip(),
        "blog": request.headers.get("X-Blog-Key", "").strip(),
    }


def is_management(key: str) -> bool:
    return bool(MANAGEMENT_KEY) and key == MANAGEMENT_KEY


def is_blog(key: str) -> bool:
    return key == BLOG_KEY


def is_author_or_management(key: str) -> bool:
    """Блог доступен по BLOG_KEY или MANAGEMENT_KEY."""
    return is_blog(key) or is_management(key)


def is_management_only(key: str) -> bool:
    """Код — только по MANAGEMENT_KEY."""
    return is_management(key)


def check_author(request: Request):
    """Блог: BLOG_KEY или MANAGEMENT_KEY."""
    key = request.headers.get("X-Author-Key", "").strip()
    if not key:
        raise HTTPException(status_code=401, detail="Требуется ключ автора")
    if not is_author_or_management(key):
        raise HTTPException(status_code=403, detail="Неверный ключ автора")


def check_management(request: Request):
    """Код и Управление: только MANAGEMENT_KEY."""
    key = request.headers.get("X-Author-Key", "").strip()
    if not MANAGEMENT_KEY:
        raise HTTPException(status_code=503, detail="MANAGEMENT_KEY не настроен на сервере")
    if key != MANAGEMENT_KEY:
        raise HTTPException(status_code=403, detail="Требуется ключ Управления")


def _pick_model_tier(user_message: str, carried_metrics: Optional[Dict[str, Any]], models: Dict[str, str]) -> str:
    text = (user_message or "").lower()
    heavy_keywords = [
        "статья", "лонгрид", "пост", "напиши",
        "проанализируй", "анализ", "план", "стратег",
        "архитектур", "спроектируй", "разработай",
        "документ", "тз", "отчёт", "отчет",
        "промпт", "layer", "код", "app.py", "index.html",
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


def pick_provider_and_model(body: Dict[str, Any], user_message: str, carried_metrics: Optional[Dict[str, Any]] = None):
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


# НОВОЕ: базовые метрики с лотами, trust, уведомлениями, carried/open
BASE_METRICS = {
    "stability_index": 0.0,
    "indicator_status": "success",
    "cycles_completed": 0,
    "collisions_resolved": "0/0",
    "lots": {"balance": "+0.0", "history": []},
    "patterns_applied": [],
    "cognitive_distortions": [],
    "autonomy_levels": [],
    "mind_scale": "micro",
    "human_contribution": 0.0,
    "value_choices": [],
    "consequences_tree": None,
    "timeline": None,
    "matrix": None,
    "dilemma_type": None,
    "impact_map": None,
    "reset_proposal": None,
    "artifact_status": None,
    "required_skills": [],
    "risk_intercept": None,
    "reasoning_trace": None,
    "breakthrough_marker": False,
    "cognitive_pulse": "stable",
    "protocol_integrity": True,
    "management_mode": False,
    "extended_metrics": None,
    "mode_suggested": "analyst",
    "reminder": None,
    "artifacts": [],
    "ideas": [],
    "dimension": None,
    "priority_drift": None,
    "wish_map": None,
    "social_adaptation": {"active": False, "reason": None, "level": "inactive"},
    "dominant_trait": {
        "detected": False, "influence": None, "risk": None,
        "stability_delta": 0.0, "hint": None, "steps": [],
    },
    "hidden_assumptions": [],
    "stage": None,
    "trust_check": None,
    "dev_alert": None,
    "passport": {
        "level": "micro", "title": None, "goal": None, "result": None,
        "mission": None, "values": [], "constraints": [], "stakeholders": [],
        "risks": [], "metrics": [], "completion": 0,
    },
    "profile": {
        "values": {}, "patterns": [], "distortions": [], "insights": [],
        "somatic": {"energy": 0.5, "tension": 0.3, "focus": 0.5, "mood": None, "note": None},
        "skills": [],
        "trust_levels": {},
    },
}


# НОВОЕ: схема с новыми полями
COMPACT_SCHEMA = {
    "stability_index": "float 0-1",
    "indicator_status": "success | warning | critical",
    "cycles_completed": "int",
    "collisions_resolved": "N/N",
    "lots": "{balance: '+X.X', history: [{at, delta, reason, type}]}",
    "mind_scale": "micro | tactical | strategic | systemic",
    "human_contribution": "float 0-1",
    "cognitive_pulse": "slow | stable | fast",
    "mode_suggested": "analyst | strategist | neutral",
    "reasoning_trace": "string | null",
    "breakthrough_marker": "bool",
    "hidden_assumptions": "[string]",
    "stage": "string | null",
    "trust_check": "{action, category, level_required, level_user, allowed, reason} | null",
    "dev_alert": "{id, at, type, severity, title, detail, solution, revision, actions, visible_to, status} | null",
    "reset_proposal": "{recommended, reset_point, reason, return_to_decision} | null",
    "reminder": "{set, at, text} | null",
    "artifact_status": "{type, title, ready, suggested_tags, format, path, language, edit} | null",
    "value_choices": "[{question, dilemma_type, options: [{label, text, recommended, experimental, consequences}]}]",
    "consequences_tree": "{root, branches} | null",
    "timeline": "[{horizon, effects}] | null",
    "matrix": "{dimensions, options: [{label, scores}]} | null",
    "risk_intercept": "{active, requested_action, risk_level, damage_level, safe_alternative} | null",
    "social_adaptation": "{active, reason, level}",
    "dominant_trait": "{detected, influence, risk, stability_delta, hint, steps}",
    "dimension": "{active, related, warning} | null",
    "priority_drift": "{detected, current, preferred, reason, action} | null",
    "ideas": "[{id, text, status}]",
    "wish_map": "{active, needs: [{type, text, source, confidence}]} | null",
    "autonomy_levels": "[{action, level, status}]",
    "extended_metrics": "{stability_index, stage, technical, patterns, hidden_assumptions, open} | null",
    "passport": {
        "level": "micro | tactical | strategic | systemic",
        "title": "string | null", "goal": "string | null", "result": "string | null",
        "mission": "string | null",
        "values": "[string]", "constraints": "[string]", "stakeholders": "[string]",
        "risks": "[string]", "metrics": "[string]",
        "completion": "int 0-100",
    },
    "profile": {
        "values": "{развитие, стабильность, свобода, контроль, связь: 0-1}",
        "patterns": "[string]", "distortions": "[string]", "insights": "[string]",
        "somatic": "{energy, tension, focus, mood, note}",
        "skills": "[string]",
        "trust_levels": "{analytics, artifacts, technical, communications, financial: 0-4}",
    },
    "artifacts": "[{id, name, type, format, stage, version, comment, path, language, diff_from_previous, versions}]",
}


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
                    fixed = re.sub(r'(?<!\\)\n', '\\\\n', chunk)
                    try:
                        return json.loads(fixed)
                    except Exception:
                        return None
    return None


def compact_carried(carried: Optional[Dict[str, Any]]) -> Dict[str, Any]:
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
            "trust_levels": pr.get("trust_levels") or {},
        }
    arts = carried.get("artifacts") or []
    if arts:
        compacted_arts = []
        for a in arts[-3:]:
            if not isinstance(a, dict):
                continue
            item = {
                "id": a.get("id"), "name": a.get("name"), "type": a.get("type"),
                "version": a.get("version"), "stage": a.get("stage"),
                "path": a.get("path"), "language": a.get("language"),
            }
            content = a.get("content") or ""
            if content and len(content) < 12000:
                item["content"] = content
            compacted_arts.append(item)
        out["artifacts"] = compacted_arts

    # НОВОЕ: сжатый контекст из прошлых сессий
    if carried.get("dimensions"):
        out["dimensions"] = carried["dimensions"]
    if carried.get("packages_active"):
        out["packages_active"] = carried["packages_active"]
    if carried.get("last_decisions"):
        out["last_decisions"] = carried["last_decisions"]
    return out


def merge_metrics(incoming: Dict[str, Any], carried: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    carried = carried or {}
    result = {**BASE_METRICS, **carried}

    skip_keys = (
        "passport", "profile", "reminder", "artifacts", "social_adaptation",
        "dominant_trait", "ideas", "dimension", "priority_drift", "wish_map",
        "lots", "trust_check", "dev_alert",
    )
    for k, v in (incoming or {}).items():
        if k in skip_keys:
            continue
        if v is not None:
            result[k] = v

    # social_adaptation
    inc_sa = (incoming or {}).get("social_adaptation")
    if isinstance(inc_sa, dict):
        result["social_adaptation"] = {
            "active": bool(inc_sa.get("active")),
            "reason": inc_sa.get("reason"),
            "level": inc_sa.get("level", "inactive"),
        }
    else:
        result["social_adaptation"] = carried.get("social_adaptation") or BASE_METRICS["social_adaptation"]

    # dominant_trait
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

    # ideas
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

    # dimension
    inc_dim = (incoming or {}).get("dimension")
    result["dimension"] = inc_dim if inc_dim is not None else carried.get("dimension")

    # priority_drift
    inc_pd = (incoming or {}).get("priority_drift")
    result["priority_drift"] = inc_pd if inc_pd is not None else carried.get("priority_drift")

    # wish_map — перезапись
    inc_wm = (incoming or {}).get("wish_map")
    result["wish_map"] = inc_wm if inc_wm is not None else carried.get("wish_map")

    # НОВОЕ: lots
    inc_lots = (incoming or {}).get("lots") or {}
    car_lots = carried.get("lots") or {"balance": "+0.0", "history": []}
    merged_lots = {"balance": inc_lots.get("balance") or car_lots.get("balance") or "+0.0", "history": []}
    old_hist = list(car_lots.get("history") or [])
    new_hist = inc_lots.get("history") or []
    seen_lots = set()
    for item in old_hist + new_hist:
        if not isinstance(item, dict):
            continue
        key = (item.get("at"), item.get("reason"), item.get("delta"))
        if key in seen_lots:
            continue
        seen_lots.add(key)
        old_hist.append(item)
    merged_lots["history"] = list({(i.get("at"), i.get("reason")): i for i in old_hist if isinstance(i, dict)}.values())
    result["lots"] = merged_lots

    # НОВОЕ: trust_check — перезапись
    inc_tc = (incoming or {}).get("trust_check")
    result["trust_check"] = inc_tc if inc_tc is not None else carried.get("trust_check")

    # НОВОЕ: dev_alert — перезапись (новое уведомление)
    inc_da = (incoming or {}).get("dev_alert")
    if inc_da is not None:
        result["dev_alert"] = inc_da
    else:
        result["dev_alert"] = carried.get("dev_alert")

    # passport
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

    # profile
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
    # НОВОЕ: trust_levels в profile
    if isinstance(inc_prof.get("trust_levels"), dict) and inc_prof["trust_levels"]:
        merged_prof["trust_levels"] = {**(merged_prof.get("trust_levels") or {}), **inc_prof["trust_levels"]}
    result["profile"] = merged_prof

    # reminder
    inc_rem = (incoming or {}).get("reminder")
    result["reminder"] = inc_rem if inc_rem is not None else carried.get("reminder")

    # artifacts
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


# НОВОЕ: сжатие контекста для carried_metrics в ответ
def build_carried_for_response(metrics: Dict[str, Any]) -> Dict[str, Any]:
    """Возвращает сжатый carried_metrics для следующего запроса."""
    return {
        "passport": metrics.get("passport") or {},
        "profile": metrics.get("profile") or {},
        "artifacts": [
            {k: v for k, v in a.items() if k in ("id", "name", "type", "version", "stage", "path", "language")}
            for a in (metrics.get("artifacts") or [])[-3:]
            if isinstance(a, dict)
        ],
        "trust_levels": (metrics.get("profile") or {}).get("trust_levels") or {},
        "lots": metrics.get("lots") or {"balance": "+0.0", "history": []},
        "dimension": metrics.get("dimension"),
    }


# НОВОЕ: построение системного промпта с LAYER_B и схемами
def build_system_prompt(extended: bool = False, management: bool = False) -> str:
    parts = [
        "Ты — когнитивный AI-партнёр Monolog. ",
        "Отвечай ТОЛЬКО валидным JSON, без пояснений и размышлений. ",
        "Ничего до { и ничего после }. ",
        "Формат строго: {\"reply_text\": \"...\", \"metrics\": {...}, \"carried_metrics\": {...}, \"open_threads\": [...]}\n",
        "reply_text — Markdown-текст ответа на русском языке. ",
        "Не сжимай итоговый ответ — сжатие только для анализа. ",
        "metrics — строго по схеме ниже. Все поля обязательны.\n\n",
    ]
    if LAYER_A:
        parts.append(f"=== СЛОЙ A ===\n{LAYER_A}\n\n")
    if LAYER_B:
        parts.append(f"=== СЛОЙ B (методология, достраивается по якорям) ===\n{LAYER_B}\n\n")
    if SCHEMAS.get("trust"):
        parts.append(f"=== TRUST MATRIX ===\n{json.dumps(SCHEMAS['trust'], ensure_ascii=False)}\n\n")
    if SCHEMAS.get("artifacts"):
        parts.append(f"=== АРТЕФАКТЫ ===\n{json.dumps(SCHEMAS['artifacts'], ensure_ascii=False)}\n\n")
    if management and SCHEMAS.get("management"):
        parts.append(f"=== УПРАВЛЕНИЕ ===\n{json.dumps(SCHEMAS['management'], ensure_ascii=False)}\n\n")
    parts.append(f"=== СХЕМА METRICS ===\n{json.dumps(COMPACT_SCHEMA, ensure_ascii=False)}")
    return "".join(parts)


async def call_provider(messages: List[Dict[str, str]], api_key: str, base_url: str, model: str, provider: str) -> str:
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    if provider == "openrouter":
        headers["HTTP-Referer"] = "https://agent-23r6.onrender.com"
        headers["X-Title"] = "AI Monolog"

    payload = {"model": model, "messages": messages, "max_tokens": MAX_TOKENS, "temperature": 0.6}

    cfg = PROVIDERS.get(provider, {})
    if cfg.get("reasoning_effort"):
        if model.startswith("openai/gpt-oss") or model.startswith("gpt-oss"):
            payload["reasoning_effort"] = "low"
        elif model.startswith("qwen"):
            payload["reasoning_effort"] = "none"

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        r = await client.post(base_url, headers=headers, json=payload)

    remaining = r.headers.get("x-ratelimit-remaining-tokens", "?")
    log.info(f"Provider [{provider}/{model}] | status={r.status_code} | remaining={remaining}")

    if r.status_code == 429:
        retry_after = r.headers.get("retry-after")
        if retry_after:
            detail = f"Лимит исчерпан. Повторите через {retry_after} сек. Или введите свой ключ в настройках."
        else:
            detail = "Дневной лимит ключа исчерпан. Он сбросится в полночь UTC (03:00 МСК). Или введите свой ключ в настройках."
        raise HTTPException(status_code=429, detail=detail)
    if r.status_code == 402:
        raise HTTPException(status_code=402, detail="Недостаточно кредитов. Пополните баланс или смените провайдера.")
    if r.status_code >= 400:
        log.error(f"Provider error {r.status_code}: {r.text[:300]}")
        raise HTTPException(status_code=r.status_code, detail=f"Ошибка {PROVIDERS.get(provider, {}).get('name', provider)} API")

    data = r.json()
    return strip_thinking(data["choices"][0]["message"]["content"])


# --- GitHub API ---
GITHUB_API = "https://api.github.com"
_blog_cache = {"posts": None, "sha": None, "fetched_at": 0}
BLOG_CACHE_TTL = 300


async def github_get_file():
    now = time.time()
    if _blog_cache["posts"] is not None and (now - _blog_cache["fetched_at"]) < BLOG_CACHE_TTL:
        return _blog_cache["posts"], _blog_cache.get("sha")

    url = f"{GITHUB_API}/repos/{GITHUB_REPO}/contents/{BLOG_PATH}"
    headers = {"Accept": "application/vnd.github+json"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"

    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get(url, headers=headers, params={"ref": GITHUB_BRANCH})

    if r.status_code == 404:
        return [], None
    if r.status_code >= 400:
        raise HTTPException(status_code=502, detail="Не удалось прочитать блог из GitHub")

    data = r.json()
    try:
        raw = base64.b64decode(data.get("content", "")).decode("utf-8")
        posts = json.loads(raw) if raw.strip() else []
    except Exception:
        posts = []

    _blog_cache["posts"] = posts
    _blog_cache["sha"] = data.get("sha")
    _blog_cache["fetched_at"] = now
    return posts, data.get("sha")


async def github_put_file(posts: list, message: str, branch: str = None):
    if not GITHUB_TOKEN:
        raise HTTPException(status_code=503, detail="GITHUB_TOKEN не настроен")

    branch = branch or GITHUB_BRANCH
    _, sha = await github_get_file()
    content = json.dumps(posts, ensure_ascii=False, indent=2)
    content_b64 = base64.b64encode(content.encode("utf-8")).decode("utf-8")

    url = f"{GITHUB_API}/repos/{GITHUB_REPO}/contents/{BLOG_PATH}"
    headers = {"Accept": "application/vnd.github+json", "Authorization": f"Bearer {GITHUB_TOKEN}"}
    body = {"message": message, "content": content_b64, "branch": branch}
    if sha:
        body["sha"] = sha

    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.put(url, headers=headers, json=body)

    if r.status_code >= 400:
        raise HTTPException(status_code=502, detail="Не удалось сохранить блог в GitHub")

    _blog_cache["posts"] = posts
    _blog_cache["sha"] = r.json().get("content", {}).get("sha")
    _blog_cache["fetched_at"] = time.time()
    return True


app = FastAPI(title="Monolog MVP")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.get("/")
async def root():
    return FileResponse("index.html")


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "dev_keys": len(_DEV_KEYS_GROQ),
        "byok": ALLOW_BYOK,
        "blog_ready": bool(GITHUB_TOKEN),
        "blog_key_set": bool(BLOG_KEY),
        "management_key_set": bool(MANAGEMENT_KEY),
        "providers": list(PROVIDERS.keys()),
        "layer_a_loaded": bool(LAYER_A),
        "layer_b_loaded": bool(LAYER_B),
        "schemas_loaded": [k for k, v in SCHEMAS.items() if v],
    }


@app.get("/providers")
async def providers_info():
    return JSONResponse({
        "providers": [
            {"id": "groq", "name": "Groq", "url": "https://console.groq.com/keys", "free": "1000/день",
             "steps": ["Открой console.groq.com", "Зарегистрируйся", "API Keys", "Create API Key", "Скопируй ключ"]},
            {"id": "openrouter", "name": "OpenRouter", "url": "https://openrouter.ai/keys", "free": "50/день",
             "steps": ["Открой openrouter.ai", "Регистрация", "Keys", "Create Key", "Скопируй ключ"]},
            {"id": "cerebras", "name": "Cerebras", "url": "https://cloud.cerebras.ai", "free": "14400/день",
             "steps": ["Открой cloud.cerebras.ai", "Регистрация", "API Keys", "Generate", "Скопируй ключ"]},
            {"id": "sambanova", "name": "SambaNova", "url": "https://cloud.sambanova.ai", "free": "12000/день",
             "steps": ["Открой cloud.sambanova.ai", "Регистрация", "API Keys", "Create", "Скопируй ключ"]},
        ]
    })


@app.post("/chat")
async def chat(request: Request):
    body = await request.json()
    user_message = (body.get("message") or "").strip()
    attachments = body.get("attachments") or []
    carried_metrics = body.get("carried_metrics") or {}
    open_threads = body.get("open_threads") or []

    if not user_message and not attachments:
        raise HTTPException(status_code=400, detail="Пустое сообщение")

    provider, base_url, model, api_key, source = pick_provider_and_model(body, user_message, carried_metrics)
    if not api_key:
        raise HTTPException(status_code=503, detail="Нет доступных ключей. Введите свой ключ в настройках.")

    # НОВОЕ: разведение ключей
    blog_key = (body.get("blog_key") or "").strip()
    management_key = (body.get("management_key") or "").strip()
    extended_metrics = is_blog(blog_key) or is_management(management_key)
    management_mode = is_management(management_key)

    log.info(f"Chat | provider={provider} | source={source} | model={model} | management={management_mode} | extended={extended_metrics}")

    compacted = compact_carried(carried_metrics)
    system_prompt = build_system_prompt(extended=extended_metrics, management=management_mode)
    messages = [{"role": "system", "content": system_prompt}]

    user_content = user_message or "Проанализируй вложения."
    if attachments:
        block = "\n\n=== ВЛОЖЕНИЯ ===\n"
        for a in attachments[:3]:
            block += f"\n[Файл: {a.get('name', 'без имени')}]\n{a.get('text', '')}\n"
        user_content += block

    if compacted:
        user_content += "\n\n=== СЖАТЫЙ КОНТЕКСТ ПРОЕКТА ===\n" + json.dumps(compacted, ensure_ascii=False)
    if open_threads:
        user_content += "\n\n=== КЛАСС ПРОБЛЕМ (достройка) ===\n" + json.dumps(open_threads, ensure_ascii=False)

    messages.append({"role": "user", "content": user_content})

    raw = await call_provider(messages, api_key, base_url, model, provider)
    parsed = extract_json(raw)

    if parsed and "reply_text" in parsed:
        metrics = merge_metrics(parsed.get("metrics") or {}, carried_metrics)
        metrics["management_mode"] = management_mode
        if extended_metrics:
            metrics["extended_metrics"] = metrics.get("extended_metrics") or parsed.get("metrics", {}).get("extended_metrics")

        carried_out = build_carried_for_response(metrics)
        threads_out = parsed.get("open_threads") or open_threads

        return JSONResponse({
            "reply_text": parsed["reply_text"],
            "metrics": metrics,
            "carried_metrics": carried_out,
            "open_threads": threads_out,
            "key_source": source,
            "provider_used": provider,
            "model_used": model,
            "management_mode": management_mode,
            "extended_metrics": extended_metrics,
        })

    log.warning(f"JSON parse failed. Raw (first 500): {raw[:500]}")

    fallback_text = None
    m2 = re.search(r'"reply_text"\s*:\s*"((?:[^"\\]|\\.)*)"', raw, re.DOTALL)
    if m2:
        try:
            fallback_text = json.loads('"' + m2.group(1) + '"')
        except Exception:
            fallback_text = m2.group(1).replace("\\n", "\n").replace('\\"', '"')

    if not fallback_text:
        fallback_text = "Извините, произошла ошибка обработки ответа. Попробуйте ещё раз или переформулируйте запрос."

    fallback_metrics = merge_metrics({}, carried_metrics)
    fallback_metrics["protocol_integrity"] = False
    fallback_metrics["indicator_status"] = "warning"
    fallback_metrics["management_mode"] = management_mode

    return JSONResponse({
        "reply_text": fallback_text,
        "metrics": fallback_metrics,
        "carried_metrics": build_carried_for_response(fallback_metrics),
        "open_threads": open_threads,
        "key_source": source,
        "provider_used": provider,
        "model_used": model,
        "management_mode": management_mode,
        "extended_metrics": extended_metrics,
    })


@app.post("/export/docx")
async def export_docx(request: Request):
    try:
        from docx import Document
        from docx.shared import Pt
    except ImportError:
        raise HTTPException(status_code=503, detail="python-docx не установлен")

    body = await request.json()
    title = (body.get("title") or "Документ").strip()
    text = (body.get("body") or "").strip()

    if not text:
        raise HTTPException(status_code=400, detail="Пустой текст")

    doc = Document()
    if title:
        doc.add_heading(title, level=0)

    for line in text.split("\n"):
        s = line.rstrip()
        if not s:
            continue
        if s.startswith("# "):
            doc.add_heading(s[2:].strip(), level=1)
        elif s.startswith("## "):
            doc.add_heading(s[3:].strip(), level=2)
        elif s.startswith("### "):
            doc.add_heading(s[4:].strip(), level=3)
        elif s.startswith("- ") or s.startswith("* "):
            doc.add_paragraph(s[2:].strip(), style="List Bullet")
        elif re.match(r"^\d+\.\s", s):
            doc.add_paragraph(re.sub(r"^\d+\.\s", "", s), style="List Number")
        else:
            p = doc.add_paragraph(s)
            for run in p.runs:
                run.font.size = Pt(11)

    buf = BytesIO()
    doc.save(buf)
    buf.seek(0)

    safe_title = re.sub(r"[^\w\-]+", "_", title or "document")[:60]
    filename = f"{safe_title}.docx"

    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# --- Blog endpoints ---
@app.get("/blog")
async def blog_list():
    posts, _ = await github_get_file()
    metas = []
    for p in posts:
        metas.append({
            "id": p.get("id"), "title": p.get("title"),
            "tags": p.get("tags", []), "author": p.get("author", "Эльвира"),
            "created_at": p.get("created_at"), "updated_at": p.get("updated_at"),
            "preview": (p.get("body") or "")[:180], "cover": p.get("cover"),
        })
    metas.sort(key=lambda x: x.get("created_at") or "", reverse=True)
    return JSONResponse({"posts": metas, "count": len(metas)})


@app.get("/blog/{post_id}")
async def blog_get(post_id: str):
    posts, _ = await github_get_file()
    for p in posts:
        if p.get("id") == post_id:
            return JSONResponse(p)
    raise HTTPException(status_code=404, detail="Статья не найдена")


@app.post("/blog/publish")
async def blog_publish(request: Request):
    check_author(request)  # BLOG_KEY или MANAGEMENT_KEY
    body = await request.json()
    title = (body.get("title") or "").strip()
    text = (body.get("body") or "").strip()
    tags = body.get("tags") or []
    author = (body.get("author") or "Эльвира").strip()

    if not title or not text:
        raise HTTPException(status_code=400, detail="Нужны заголовок и текст")

    posts, _ = await github_get_file()
    post_id = "post_" + str(int(time.time() * 1000))
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    new_post = {
        "id": post_id, "title": title, "body": text,
        "tags": tags if isinstance(tags, list) else [],
        "author": author, "created_at": now, "updated_at": now,
    }
    posts.append(new_post)
    await github_put_file(posts, f"Blog: publish '{title[:50]}'")
    return JSONResponse({"ok": True, "id": post_id})


@app.put("/blog/{post_id}")
async def blog_update(post_id: str, request: Request):
    check_author(request)
    body = await request.json()
    posts, _ = await github_get_file()

    found = None
    for p in posts:
        if p.get("id") == post_id:
            found = p
            break
    if not found:
        raise HTTPException(status_code=404, detail="Статья не найдена")

    if "title" in body and body["title"] is not None:
        found["title"] = (body["title"] or "").strip()
    if "body" in body and body["body"] is not None:
        found["body"] = body["body"]
    if "tags" in body and isinstance(body["tags"], list):
        found["tags"] = body["tags"]
    found["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    await github_put_file(posts, f"Blog: update '{post_id}'")
    return JSONResponse({"ok": True, "id": post_id})


@app.delete("/blog/{post_id}")
async def blog_delete(post_id: str, request: Request):
    check_author(request)
    posts, _ = await github_get_file()
    new_posts = [p for p in posts if p.get("id") != post_id]
    if len(new_posts) == len(posts):
        raise HTTPException(status_code=404, detail="Статья не найдена")
    await github_put_file(new_posts, f"Blog: delete '{post_id}'")
    return JSONResponse({"ok": True})


# --- Code endpoints (Пакет разработчика, ветка dev) ---
@app.get("/code/read")
async def code_read(request: Request, path: str, branch: str = None):
    check_management(request)  # только MANAGEMENT_KEY
    if not GITHUB_TOKEN:
        raise HTTPException(status_code=503, detail="GITHUB_TOKEN не настроен")

    branch = branch or CODE_BRANCH
    url = f"{GITHUB_API}/repos/{GITHUB_REPO}/contents/{path}"
    headers = {"Accept": "application/vnd.github+json", "Authorization": f"Bearer {GITHUB_TOKEN}"}
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get(url, headers=headers, params={"ref": branch})
        branch_used = branch
        if r.status_code == 404 and branch == CODE_BRANCH:
            r = await client.get(url, headers=headers, params={"ref": GITHUB_BRANCH})
            branch_used = GITHUB_BRANCH

    if r.status_code == 404:
        return JSONResponse({"exists": False, "path": path, "content": None, "sha": None, "branch": branch_used})
    if r.status_code >= 400:
        raise HTTPException(status_code=502, detail="Не удалось прочитать файл")

    data = r.json()
    try:
        content = base64.b64decode(data.get("content", "")).decode("utf-8")
    except Exception:
        content = ""

    return JSONResponse({"exists": True, "path": path, "content": content, "sha": data.get("sha"), "branch": branch_used})


@app.post("/code/save")
async def code_save(request: Request):
    check_management(request)
    if not GITHUB_TOKEN:
        raise HTTPException(status_code=503, detail="GITHUB_TOKEN не настроен")

    body = await request.json()
    path = (body.get("path") or "").strip()
    content = body.get("content") or ""
    message = (body.get("message") or f"Update {path} via Monolog").strip()
    branch = (body.get("branch") or CODE_BRANCH).strip()

    if not path:
        raise HTTPException(status_code=400, detail="Не указан путь")

    url = f"{GITHUB_API}/repos/{GITHUB_REPO}/contents/{path}"
    headers = {"Accept": "application/vnd.github+json", "Authorization": f"Bearer {GITHUB_TOKEN}"}

    sha = None
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get(url, headers=headers, params={"ref": branch})
        if r.status_code == 200:
            sha = r.json().get("sha")

    content_b64 = base64.b64encode(content.encode("utf-8")).decode("utf-8")
    payload = {"message": message, "content": content_b64, "branch": branch}
    if sha:
        payload["sha"] = sha

    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.put(url, headers=headers, json=payload)

    if r.status_code >= 400:
        raise HTTPException(status_code=502, detail="Не удалось сохранить код в GitHub")

    data = r.json()
    return JSONResponse({
        "ok": True, "path": path, "branch": branch,
        "commit_sha": data.get("commit", {}).get("sha"),
        "html_url": data.get("commit", {}).get("html_url"),
    })


# --- НОВОЕ: Prompt endpoints ---
@app.get("/prompt/read")
async def prompt_read(request: Request, path: str):
    check_management(request)
    if not GITHUB_TOKEN:
        raise HTTPException(status_code=503, detail="GITHUB_TOKEN не настроен")
    return await code_read(request, path=path)


@app.post("/prompt/save")
async def prompt_save(request: Request):
    check_management(request)
    if not GITHUB_TOKEN:
        raise HTTPException(status_code=503, detail="GITHUB_TOKEN не настроен")

    body = await request.json()
    path = (body.get("path") or "").strip()
    content = body.get("content") or ""
    if not path:
        raise HTTPException(status_code=400, detail="Не указан путь")
    if not path.startswith(f"{PROMPTS_DIR}/") and not path.startswith(f"{SCHEMAS_DIR}/") and not path.endswith(".md"):
        raise HTTPException(status_code=400, detail="Путь должен быть в prompts/ или schemas/")

    result = await code_save(request)
    return result


# --- НОВОЕ: Infrastructure ---
@app.get("/infrastructure")
async def infrastructure(request: Request):
    check_management(request)
    if not GITHUB_TOKEN:
        raise HTTPException(status_code=503, detail="GITHUB_TOKEN не настроен")
    return await code_read(request, path="infrastructure.md")


# --- НОВОЕ: Files list ---
@app.get("/files/list")
async def files_list(request: Request, path: str = ""):
    check_management(request)
    if not GITHUB_TOKEN:
        raise HTTPException(status_code=503, detail="GITHUB_TOKEN не настроен")

    url = f"{GITHUB_API}/repos/{GITHUB_REPO}/contents/{path}"
    headers = {"Accept": "application/vnd.github+json", "Authorization": f"Bearer {GITHUB_TOKEN}"}
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get(url, headers=headers, params={"ref": CODE_BRANCH})

    if r.status_code == 404:
        return JSONResponse({"path": path, "items": []})
    if r.status_code >= 400:
        raise HTTPException(status_code=502, detail="Не удалось получить список файлов")

    items = []
    for item in r.json():
        items.append({"name": item.get("name"), "path": item.get("path"), "type": item.get("type"), "size": item.get("size")})
    return JSONResponse({"path": path, "items": items})


# --- НОВОЕ: Commit history ---
@app.get("/commit/history")
async def commit_history(request: Request, path: str = "", limit: int = 10):
    check_management(request)
    if not GITHUB_TOKEN:
        raise HTTPException(status_code=503, detail="GITHUB_TOKEN не настроен")

    url = f"{GITHUB_API}/repos/{GITHUB_REPO}/commits"
    headers = {"Accept": "application/vnd.github+json", "Authorization": f"Bearer {GITHUB_TOKEN}"}
    params = {"sha": CODE_BRANCH, "per_page": limit}
    if path:
        params["path"] = path

    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get(url, headers=headers, params=params)

    if r.status_code >= 400:
        raise HTTPException(status_code=502, detail="Не удалось получить историю коммитов")

    commits = []
    for c in r.json():
        commits.append({
            "sha": c.get("sha"),
            "message": (c.get("commit") or {}).get("message"),
            "author": (c.get("commit") or {}).get("author", {}).get("name"),
            "date": (c.get("commit") or {}).get("author", {}).get("date"),
        })
    return JSONResponse({"branch": CODE_BRANCH, "commits": commits})


# --- НОВОЕ: Branch merge / rollback ---
@app.post("/branch/merge")
async def branch_merge(request: Request):
    check_management(request)
    if not GITHUB_TOKEN:
        raise HTTPException(status_code=503, detail="GITHUB_TOKEN не настроен")

    body = await request.json()
    head = (body.get("head") or CODE_BRANCH).strip()
    base = (body.get("base") or GITHUB_BRANCH).strip()
    message = (body.get("message") or f"Merge {head} -> {base} via Monolog").strip()

    url = f"{GITHUB_API}/repos/{GITHUB_REPO}/merges"
    headers = {"Accept": "application/vnd.github+json", "Authorization": f"Bearer {GITHUB_TOKEN}"}
    payload = {"base": base, "head": head, "commit_message": message}

    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post(url, headers=headers, json=payload)

    if r.status_code == 204:
        return JSONResponse({"ok": True, "message": "Всё уже синхронизировано"})
    if r.status_code >= 400:
        raise HTTPException(status_code=502, detail=f"Ошибка мержа: {r.text[:200]}")

    data = r.json()
    return JSONResponse({"ok": True, "sha": data.get("sha"), "html_url": data.get("html_url")})


@app.post("/branch/rollback")
async def branch_rollback(request: Request):
    check_management(request)
    if not GITHUB_TOKEN:
        raise HTTPException(status_code=503, detail="GITHUB_TOKEN не настроен")

    body = await request.json()
    commit_sha = (body.get("commit_sha") or "").strip()
    if not commit_sha:
        raise HTTPException(status_code=400, detail="Не указан commit_sha")

    # Откат через новый коммит с содержимым файла из указанного коммита
    path = (body.get("path") or "").strip()
    if not path:
        raise HTTPException(status_code=400, detail="Не указан path")

    url = f"{GITHUB_API}/repos/{GITHUB_REPO}/contents/{path}"
    headers = {"Accept": "application/vnd.github+json", "Authorization": f"Bearer {GITHUB_TOKEN}"}

    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get(url, headers=headers, params={"ref": commit_sha})
        if r.status_code >= 400:
            raise HTTPException(status_code=502, detail="Не удалось прочитать версию из коммита")
        old_sha = r.json().get("sha")

    # Создаём коммит с откатом
    return JSONResponse({"ok": True, "from_commit": commit_sha, "path": path, "note": "Требуется применение содержимого вручную через /code/save"})


# --- НОВОЕ: Notifications ---
# Простое хранилище в памяти для уведомлений (для счётчика).
# В проде — Supabase или файл.
_notifications_store: Dict[str, List[Dict[str, Any]]] = {}


@app.post("/notifications")
async def notifications_add(request: Request):
    check_management(request)
    body = await request.json()
    user_id = (body.get("user_id") or "default").strip()
    alert = body.get("alert") or {}
    _notifications_store.setdefault(user_id, []).append(alert)
    return JSONResponse({"ok": True, "count": len(_notifications_store[user_id])})


@app.get("/notifications")
async def notifications_list(request: Request, user_id: str = "default"):
    check_management(request)
    items = _notifications_store.get(user_id, [])
    new_count = sum(1 for i in items if i.get("status") == "new")
    return JSONResponse({"items": items, "count": len(items), "new_count": new_count})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=int(os.getenv("PORT", 8000)))