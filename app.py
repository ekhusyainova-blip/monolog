# app.py
# Monolog — stateless-прокси к 4 провайдерам LLM + блог + Word-экспорт.
# Режим Управления: ключ Эгида-Эльвира-7.
# Пакет разработчика: /code/* (в ветку dev).
# Слой B НЕ отправляется. История НЕ отправляется. Ключи не сохраняются.

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

# Увеличено для длинных документов и кода
MAX_TOKENS = 6000
TIMEOUT = 120.0

_DEV_KEYS_GROQ: List[str] = [k.strip() for k in os.getenv("GROQ_API_KEYS", "").split(",") if k.strip()]
_dev_key_cycle = itertools.cycle(_DEV_KEYS_GROQ) if _DEV_KEYS_GROQ else None
ALLOW_BYOK = os.getenv("ALLOW_BYOK", "true").lower() == "true"

# Режим Управления — ключ Эльвиры
MANAGEMENT_KEY = "Эгида-Эльвира-7"

# Блог
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "").strip()
GITHUB_REPO = os.getenv("GITHUB_REPO", "ekhusyainova-blip/monolog").strip()
GITHUB_BRANCH = os.getenv("GITHUB_BRANCH", "main").strip()
BLOG_PATH = "blog/posts.json"
AUTHOR_SECRET = os.getenv("AUTHOR_SECRET", "").strip()

# Пакет разработчика — ветка dev
CODE_BRANCH = "dev"


def _load(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip()
    except FileNotFoundError:
        log.warning(f"Prompt file not found: {path}")
        return ""

LAYER_A = _load("prompts/layer_a.txt")


def mask_key(key: str) -> str:
    if not key or len(key) < 12:
        return "***"
    return f"{key[:6]}...{key[-4:]}"


def next_dev_key() -> Optional[str]:
    if not _dev_key_cycle:
        return None
    return next(_dev_key_cycle)


def check_author(request: Request):
    if not AUTHOR_SECRET:
        raise HTTPException(status_code=503, detail="AUTHOR_SECRET не настроен на сервере")
    key = request.headers.get("X-Author-Key", "").strip()
    if key != AUTHOR_SECRET:
        raise HTTPException(status_code=403, detail="Неверный ключ автора")


def check_management(request: Request):
    """Проверка режима Управления."""
    key = request.headers.get("X-Management-Key", "").strip()
    if key != MANAGEMENT_KEY:
        raise HTTPException(status_code=403, detail="Режим Управления не активирован")


def _pick_model_tier(user_message: str, carried_metrics: Optional[Dict[str, Any]], models: Dict[str, str]) -> str:
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


BASE_METRICS = {
    "stability_index": 0.0,
    "indicator_status": "success",
    "cycles_completed": 0,
    "collisions_resolved": "0/0",
    "lots_balance": "+0.0",
    "patterns_applied": [],
    "cognitive_distortions": [],
    "autonomy_levels": [],
    "mind_scale": "micro",
    "human_contribution": 0.0,
    "value_choices": [],
    "consequences_tree": None,
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
    "mode_suggested": "analyst",  # analyst | strategist | neutral
    "reminder": None,
    "artifacts": [],
    "ideas": [],
    "dimension": None,
    "priority_drift": None,
    "mood_board": None,
    "social_adaptation": {
        "active": False,
        "reason": None,
        "level": "inactive",
    },
    "dominant_trait": {
        "detected": False,
        "influence": None,
        "risk": None,
        "stability_delta": 0.0,
        "hint": None,
        "steps": [],
    },
    "passport": {
        "level": "micro", "title": None, "goal": None, "result": None,
        "mission": None, "values": [], "constraints": [], "stakeholders": [],
        "risks": [], "metrics": [], "completion": 0,
    },
    "profile": {
        "values": {}, "patterns": [], "distortions": [], "insights": [],
        "somatic": {
            "energy": 0.5, "tension": 0.3, "focus": 0.5,
            "mood": None, "note": None,
        },
        "skills": [],
    },
}


COMPACT_SCHEMA = {
    "stability_index": "float 0-1",
    "indicator_status": "success | warning | critical",
    "cycles_completed": "int",
    "collisions_resolved": "N/N",
    "lots_balance": "+X.X",
    "mind_scale": "micro | tactical | strategic | systemic",
    "human_contribution": "float 0-1",
    "cognitive_pulse": "slow | stable | fast",
    "mode_suggested": "analyst | strategist | neutral",
    "reasoning_trace": "string | null",
    "breakthrough_marker": "bool",
    "reset_proposal": "{recommended, reset_point, reason} | null",
    "reminder": "{set, at, text} | null",
    "artifact_status": "{type, title, ready, suggested_tags, format, path, language, edit} | null",
    "value_choices": "[{question, dilemma_type, options: [{label, recommended, consequences}]}]",
    "risk_intercept": "{active, requested_action, risk_level, safe_alternative} | null",
    "social_adaptation": "{active, reason, level}",
    "dominant_trait": "{detected, influence, risk, stability_delta, hint, steps}",
    "dimension": "{active, related, warning} | null",
    "priority_drift": "{detected, current, preferred, reason, action} | null",
    "ideas": "[{id, text, status}]",
    "mood_board": "{active, wish, options} | null",
    "passport": {
        "level": "micro | tactical | strategic | systemic",
        "title": "string | null",
        "goal": "string | null",
        "result": "string | null",
        "mission": "string | null",
        "values": "[string]",
        "constraints": "[string]",
        "stakeholders": "[string]",
        "risks": "[string]",
        "metrics": "[string]",
        "completion": "int 0-100",
    },
    "profile": {
        "values": "{развитие: 0-1, стабильность: 0-1, свобода: 0-1, контроль: 0-1, связь: 0-1}",
        "patterns": "[string]",
        "distortions": "[string]",
        "insights": "[string]",
        "somatic": "{energy, tension, focus, mood, note}",
        "skills": "[string]",
    },
    "artifacts": "[{id, name, type, format, stage, version, comment, path, language}]",
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

    # Убираем markdown-обёртки
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```\s*$", "", text)

    # Ищем первый {
    start = text.find("{")
    if start == -1:
        return None

    # Пробуем как есть
    try:
        return json.loads(text[start:])
    except Exception:
        pass

    # Ищем сбалансированный блок
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
                    # Попытка с экранированием живых \n
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
        out["passport"] = {
            "level": p.get("level"),
            "title": p.get("title"),
            "goal": p.get("goal"),
        }
    pr = carried.get("profile") or {}
    if pr:
        out["profile"] = {
            "values": pr.get("values") or {},
            "patterns": (pr.get("patterns") or [])[:5],
        }
    arts = carried.get("artifacts") or []
    if arts:
        compacted_arts = []
        for a in arts[-3:]:
            if not isinstance(a, dict):
                continue
            item = {
                "id": a.get("id"),
                "name": a.get("name"),
                "type": a.get("type"),
                "version": a.get("version"),
                "stage": a.get("stage"),
                "path": a.get("path"),
                "language": a.get("language"),
            }
            content = a.get("content") or ""
            if content and len(content) < 12000:
                item["content"] = content
            compacted_arts.append(item)
        out["artifacts"] = compacted_arts
    return out


def merge_metrics(incoming: Dict[str, Any], carried: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    carried = carried or {}
    result = {**BASE_METRICS, **carried}

    skip_keys = ("passport", "profile", "reminder", "artifacts", "social_adaptation",
                 "dominant_trait", "ideas", "dimension", "priority_drift", "mood_board")
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

    # mood_board — перезапись
    inc_mb = (incoming or {}).get("mood_board")
    result["mood_board"] = inc_mb if inc_mb is not None else carried.get("mood_board")

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


SYSTEM_PROMPT = (
    "Ты — когнитивный AI-партнёр Monolog. "
    "Отвечай ТОЛЬКО валидным JSON, без пояснений и размышлений. "
    "Ничего до { и ничего после }. "
    "Формат строго: {\"reply_text\": \"...\", \"metrics\": {...}}\n"
    "reply_text — Markdown-текст ответа на русском языке. "
    "Не сжимай итоговый ответ — сжатие только для анализа. "
    "metrics — строго по схеме ниже. Все поля обязательны.\n\n"
    f"=== КОГНИТИВНЫЙ ПРОМПТ (СЛОИ A + B + C + D) ===\n{LAYER_A}\n\n"
    f"=== СХЕМА METRICS ===\n{json.dumps(COMPACT_SCHEMA, ensure_ascii=False)}"
)


async def call_provider(messages: List[Dict[str, str]], api_key: str, base_url: str, model: str, provider: str) -> str:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    if provider == "openrouter":
        headers["HTTP-Referer"] = "https://agent-23r6.onrender.com"
        headers["X-Title"] = "AI Monolog"

    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": MAX_TOKENS,
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
    log.info(f"Provider [{provider}/{model}] | status={r.status_code} | remaining={remaining}")

    if r.status_code == 429:
        retry_after = r.headers.get("retry-after")
        if retry_after:
            detail = f"Лимит исчерпан. Повторите через {retry_after} сек. Или введите свой ключ в настройках."
        else:
            detail = "Дневной лимит ключа исчерпан. Он сбросится в полночь UTC (03:00 МСК). Или введите свой ключ в настройках → Провайдер."
        raise HTTPException(status_code=429, detail=detail)
    if r.status_code == 402:
        raise HTTPException(status_code=402, detail="Недостаточно кредитов на провайдере. Пополните баланс или смените провайдера.")
    if r.status_code >= 400:
        log.error(f"Provider error {r.status_code}: {r.text[:300]}")
        raise HTTPException(status_code=r.status_code, detail=f"Ошибка {PROVIDERS.get(provider, {}).get('name', provider)} API")

    data = r.json()
    content = data["choices"][0]["message"]["content"]
    return strip_thinking(content)


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
    content_b64 = data.get("content", "")
    try:
        raw = base64.b64decode(content_b64).decode("utf-8")
        posts = json.loads(raw) if raw.strip() else []
    except Exception:
        posts = []

    _blog_cache["posts"] = posts
    _blog_cache["sha"] = data.get("sha")
    _blog_cache["fetched_at"] = now
    return posts, data.get("sha")


async def github_put_file(posts: list, message: str):
    if not GITHUB_TOKEN:
        raise HTTPException(status_code=503, detail="GITHUB_TOKEN не настроен")

    _, sha = await github_get_file()
    content = json.dumps(posts, ensure_ascii=False, indent=2)
    content_b64 = base64.b64encode(content.encode("utf-8")).decode("utf-8")

    url = f"{GITHUB_API}/repos/{GITHUB_REPO}/contents/{BLOG_PATH}"
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {GITHUB_TOKEN}",
    }
    body = {"message": message, "content": content_b64, "branch": GITHUB_BRANCH}
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
        "author_secret_set": bool(AUTHOR_SECRET),
        "management_key_set": bool(MANAGEMENT_KEY),
        "providers": list(PROVIDERS.keys()),
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

    if not user_message and not attachments:
        raise HTTPException(status_code=400, detail="Пустое сообщение")

    provider, base_url, model, api_key, source = pick_provider_and_model(body, user_message, carried_metrics)
    if not api_key:
        raise HTTPException(status_code=503, detail="Нет доступных ключей. Введите свой ключ в настройках.")

    management_mode = (body.get("management_key") or "").strip() == MANAGEMENT_KEY

    log.info(f"Chat | provider={provider} | source={source} | model={model} | management={management_mode}")

    compacted = compact_carried(carried_metrics)

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    user_content = user_message or "Проанализируй вложения."
    if attachments:
        block = "\n\n=== ВЛОЖЕНИЯ ===\n"
        for a in attachments[:3]:
            block += f"\n[Файл: {a.get('name', 'без имени')}]\n{a.get('text', '')}\n"
        user_content = user_content + block

    if compacted:
        user_content += "\n\n=== СЖАТЫЙ КОНТЕКСТ ПРОЕКТА ===\n" + json.dumps(compacted, ensure_ascii=False)

    messages.append({"role": "user", "content": user_content})

    raw = await call_provider(messages, api_key, base_url, model, provider)
    parsed = extract_json(raw)

    if parsed and "reply_text" in parsed:
        metrics = merge_metrics(parsed.get("metrics") or {}, carried_metrics)
        metrics["management_mode"] = management_mode
        return JSONResponse({
            "reply_text": parsed["reply_text"],
            "metrics": metrics,
            "key_source": source,
            "provider_used": provider,
            "model_used": model,
            "management_mode": management_mode,
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
        "key_source": source,
        "provider_used": provider,
        "model_used": model,
        "management_mode": management_mode,
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
            "id": p.get("id"),
            "title": p.get("title"),
            "tags": p.get("tags", []),
            "author": p.get("author", "Эльвира"),
            "created_at": p.get("created_at"),
            "updated_at": p.get("updated_at"),
            "preview": (p.get("body") or "")[:180],
            "cover": p.get("cover"),
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
    check_author(request)
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
async def code_read(request: Request, path: str):
    check_author(request)
    if not GITHUB_TOKEN:
        raise HTTPException(status_code=503, detail="GITHUB_TOKEN не настроен")

    url = f"{GITHUB_API}/repos/{GITHUB_REPO}/contents/{path}"
    headers = {"Accept": "application/vnd.github+json", "Authorization": f"Bearer {GITHUB_TOKEN}"}
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get(url, headers=headers, params={"ref": CODE_BRANCH})
        branch_used = CODE_BRANCH
        if r.status_code == 404:
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

    return JSONResponse({
        "exists": True, "path": path, "content": content,
        "sha": data.get("sha"), "branch": branch_used,
    })


@app.post("/code/save")
async def code_save(request: Request):
    check_author(request)
    if not GITHUB_TOKEN:
        raise HTTPException(status_code=503, detail="GITHUB_TOKEN не настроен")

    body = await request.json()
    path = (body.get("path") or "").strip()
    content = body.get("content") or ""
    message = (body.get("message") or f"Update {path} via Monolog").strip()

    if not path:
        raise HTTPException(status_code=400, detail="Не указан путь")

    url = f"{GITHUB_API}/repos/{GITHUB_REPO}/contents/{path}"
    headers = {"Accept": "application/vnd.github+json", "Authorization": f"Bearer {GITHUB_TOKEN}"}

    sha = None
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get(url, headers=headers, params={"ref": CODE_BRANCH})
        if r.status_code == 200:
            sha = r.json().get("sha")

    content_b64 = base64.b64encode(content.encode("utf-8")).decode("utf-8")
    payload = {"message": message, "content": content_b64, "branch": CODE_BRANCH}
    if sha:
        payload["sha"] = sha

    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.put(url, headers=headers, json=payload)

    if r.status_code >= 400:
        raise HTTPException(status_code=502, detail="Не удалось сохранить код в GitHub")

    data = r.json()
    return JSONResponse({
        "ok": True, "path": path, "branch": CODE_BRANCH,
        "commit_sha": data.get("commit", {}).get("sha"),
        "html_url": data.get("commit", {}).get("html_url"),
    })


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=int(os.getenv("PORT", 8000)))