# app.py
# Monolog — когнитивный партнёр.
# Ядро 1.0. Три промпта: layer_a (system), layer_b (meta), layer_a_content_prompt (content).
# Stateless. История не отправляется. Ключи не сохраняются.
# Релиз 10+ итераций: согласованность ядра, расширенные модели, /releases, Управление, мета/контент разделены.

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

# --- Конфигурация провайдеров ---
# Каждый провайдер: base_url, три модели по уровню (light/medium/heavy), полный список моделей.
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
        "all_models": [
            "gpt-oss-20b",
            "gpt-oss-120b",
            "llama3.1-8b",
            "llama3.1-70b",
        ],
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

# --- Лимиты ---
MAX_TOKENS = 6000
META_MAX_TOKENS = 2000
TIMEOUT = 120.0

# --- Ключи разработчика (Groq) ---
_DEV_KEYS_GROQ: List[str] = [
    k.strip() for k in os.getenv("GROQ_API_KEYS", "").split(",") if k.strip()
]
_dev_key_cycle = itertools.cycle(_DEV_KEYS_GROQ) if _DEV_KEYS_GROQ else None

ALLOW_BYOK = os.getenv("ALLOW_BYOK", "true").lower() == "true"

# --- Ключ Управления ---
MANAGEMENT_KEY = os.getenv("MANAGEMENT_KEY", "").strip()

# --- GitHub для блога и кода ---
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "").strip()
GITHUB_REPO = os.getenv("GITHUB_REPO", "ekhusyainova-blip/monolog").strip()
GITHUB_BRANCH = os.getenv("GITHUB_BRANCH", "main").strip()
BLOG_PATH = "blog/posts.json"
RELEASES_PATH = "releases.json"
AUTHOR_SECRET = os.getenv("AUTHOR_SECRET", "").strip()
CODE_BRANCH = os.getenv("CODE_BRANCH", "dev").strip()


def _load(path: str) -> str:
    """Загружает промпт из файла. Если файла нет — пустая строка."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip()
    except FileNotFoundError:
        log.warning(f"Prompt file not found: {path}")
        return ""


# Три промпта ядра 1.0
LAYER_A = _load("prompts/layer_a.txt")             # system — ядро 1.0
LAYER_B = _load("prompts/layer_b.txt")             # meta — метрики (delta)
LAYER_A_CONTENT = _load("prompts/layer_a_content_prompt")  # content — reply_text


# --- Базовая схема метрик ---
BASE_METRICS = {
    "stability_index": 0.0,
    "indicator_status": "success",
    "cycles_completed": 0,
    "collisions_resolved": "0/0",
    "lots_balance": "+0.0",
    "mind_scale": "micro",
    "human_contribution": 0.0,
    "cognitive_pulse": "stable",
    "mode_suggested": "analyst",
    "reasoning_trace": None,
    "breakthrough_marker": False,
    "reset_proposal": None,
    "reminder": None,
    "artifact_status": None,
    "value_choices": [],
    "risk_intercept": None,
    "social_adaptation": {"active": False, "reason": None, "level": "inactive"},
    "dominant_trait": {
        "detected": False, "influence": None, "risk": None,
        "stability_delta": 0.0, "hint": None, "steps": [],
    },
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
    "required_skills": [],
    "index_delta": None,
}


def next_dev_key() -> Optional[str]:
    if not _dev_key_cycle:
        return None
    return next(_dev_key_cycle)


def check_author(request: Request):
    if not AUTHOR_SECRET:
        raise HTTPException(status_code=503, detail="AUTHOR_SECRET не настроен")
    key = request.headers.get("X-Author-Key", "").strip()
    if key != AUTHOR_SECRET:
        raise HTTPException(status_code=403, detail="Неверный ключ автора")


def check_management(request: Request):
    key = request.headers.get("X-Management-Key", "").strip()
    if not key or key != MANAGEMENT_KEY:
        raise HTTPException(status_code=403, detail="Режим Управления не активен")


def _pick_model_tier(
    user_message: str,
    carried_metrics: Optional[Dict[str, Any]],
    models: Dict[str, str],
) -> str:
    """Выбирает уровень модели (light/medium/heavy) по содержанию запроса."""
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


def pick_provider_and_model(
    body: Dict[str, Any],
    user_message: str,
    carried_metrics: Optional[Dict[str, Any]] = None,
):
    """Возвращает (provider, base_url, model, api_key, source)."""
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
    text = re.sub(r" thinking.*? response", "", text, flags=re.DOTALL)
    text = re.sub(r"<reasoning>.*?</reasoning>", "", text, flags=re.DOTALL)
    return text.strip()


def extract_json(text: str) -> Optional[Dict[str, Any]]:
    """Извлекает JSON из ответа модели. Устойчив к мусору."""
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


def compact_carried(carried: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Сжимает carried_metrics до минимально нужного для meta/content."""
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
        compacted = []
        for a in arts[-3:]:
            if not isinstance(a, dict):
                continue
            item = {
                "id": a.get("id"),
                "name": a.get("name"),
                "type": a.get("type"),
                "version": a.get("version"),
                "stage": a.get("stage"),
            }
            content = a.get("content") or ""
            if content and len(content) < 12000:
                item["content"] = content
            compacted.append(item)
        out["artifacts"] = compacted
    return out


def merge_metrics(
    incoming: Dict[str, Any],
    carried: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Накладывает delta (incoming) на carried. Возвращает полное состояние."""
    carried = carried or {}
    result = {**BASE_METRICS, **carried}

    skip_keys = (
        "passport", "profile", "reminder", "artifacts", "social_adaptation",
        "dominant_trait", "ideas", "dimension", "priority_drift", "mood_board",
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
        result["social_adaptation"] = (
            carried.get("social_adaptation") or BASE_METRICS["social_adaptation"]
        )

    # dominant_trait
    inc_dt = (incoming or {}).get("dominant_trait")
    if isinstance(inc_dt, dict):
        result["dominant_trait"] = {
            "detected": bool(inc_dt.get("detected")),
            "influence": inc_dt.get("influence"),
            "risk": inc_dt.get("risk"),
            "stability_delta": float(inc_dt.get("stability_delta") or 0.0),
            "hint": inc_dt.get("hint"),
            "steps": list(inc_dt.get("steps") or [])
            if isinstance(inc_dt.get("steps"), list) else [],
        }
    else:
        result["dominant_trait"] = (
            carried.get("dominant_trait") or BASE_METRICS["dominant_trait"]
        )

    # ideas — добавление по id
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

    # mood_board
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
        merged_prof["values"] = {
            **merged_prof.get("values", {}),
            **inc_prof["values"],
        }
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

    # artifacts — добавление по id
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


async def call_provider(
    messages: List[Dict[str, str]],
    api_key: str,
    base_url: str,
    model: str,
    provider: str,
    max_tokens: int = MAX_TOKENS,
) -> str:
    """Один вызов провайдера. Универсально для всех."""
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
        log.info(f"Provider [{provider}/{model}] status={r.status_code} remaining={remaining}")

        if r.status_code == 429:
            retry_after = r.headers.get("retry-after")
            if retry_after:
                detail = f"Лимит исчерпан. Повторите через {retry_after} сек. Или введите свой ключ в настройках."
            else:
                detail = "Дневной лимит исчерпан. Он сбросится в полночь UTC. Или введите свой ключ в настройках."
            raise HTTPException(status_code=429, detail=detail)
        if r.status_code == 402:
            raise HTTPException(status_code=402, detail="Недостаточно кредитов на провайдере.")
        if r.status_code >= 400:
            log.error(f"Provider error {r.status_code}: {r.text[:300]}")
            raise HTTPException(
                status_code=r.status_code,
                detail=f"Ошибка {PROVIDERS.get(provider, {}).get('name', provider)} API",
            )
        data = r.json()
        content = data["choices"][0]["message"]["content"]
        return strip_thinking(content)


async def call_meta(
    user_message: str,
    carried_metrics: Dict[str, Any],
    api_key: str,
    base_url: str,
    model: str,
    provider: str,
) -> Dict[str, Any]:
    """Meta-вызов: только метрики. Только delta. Не падает при ошибке."""
    if not LAYER_B:
        return {}
    messages = [{"role": "system", "content": LAYER_B}]
    payload = {
        "prev": compact_carried(carried_metrics),
        "msg": (user_message or "")[:200],
    }
    messages.append({
        "role": "user",
        "content": json.dumps(payload, ensure_ascii=False),
    })
    try:
        raw = await call_provider(
            messages, api_key, base_url, model, provider, max_tokens=META_MAX_TOKENS
        )
        return extract_json(raw) or {}
    except HTTPException:
        raise
    except Exception as e:
        log.warning(f"meta failed: {e}")
        return {}


async def call_content(
    user_message: str,
    full_metrics: Dict[str, Any],
    api_key: str,
    base_url: str,
    model: str,
    provider: str,
    attachments: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Content-вызов: только reply_text."""
    system = LAYER_A + "\n\n" + LAYER_A_CONTENT
    user_content = user_message or "Проанализируй вложения."
    if attachments:
        block = "\n\n=== ВЛОЖЕНИЯ ===\n"
        for a in attachments[:3]:
            block += f"\n[Файл: {a.get('name', 'без имени')}]\n{a.get('text', '')}\n"
        user_content += block
    user_content += "\n\n=== СОСТОЯНИЕ ===\n" + json.dumps(
        compact_carried(full_metrics), ensure_ascii=False
    )
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user_content},
    ]
    raw = await call_provider(
        messages, api_key, base_url, model, provider, max_tokens=MAX_TOKENS
    )
    parsed = extract_json(raw) or {}
    if "reply_text" not in parsed:
        parsed = {"reply_text": raw}
    return parsed


# --- GitHub API ---
GITHUB_API = "https://api.github.com"
_blog_cache = {"posts": None, "sha": None, "fetched_at": 0}
BLOG_CACHE_TTL = 300


async def github_get_file(path: str):
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


async def github_put_file(path: str, content_obj, message: str):
    if not GITHUB_TOKEN:
        raise HTTPException(status_code=503, detail="GITHUB_TOKEN не настроен")
    _, sha = await github_get_file(path)
    content = json.dumps(content_obj, ensure_ascii=False, indent=2)
    content_b64 = base64.b64encode(content.encode("utf-8")).decode("utf-8")
    url = f"{GITHUB_API}/repos/{GITHUB_REPO}/contents/{path}"
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
            raise HTTPException(status_code=502, detail=f"Не удалось сохранить {path}")
        return True


async def github_get_blog():
    now = time.time()
    if _blog_cache["posts"] is not None and (now - _blog_cache["fetched_at"]) < BLOG_CACHE_TTL:
        return _blog_cache["posts"], _blog_cache.get("sha")
    posts, sha = await github_get_file(BLOG_PATH)
    posts = posts or []
    _blog_cache["posts"] = posts
    _blog_cache["sha"] = sha
    _blog_cache["fetched_at"] = now
    return posts, sha


async def github_put_blog(posts: list, message: str):
    if not GITHUB_TOKEN:
        raise HTTPException(status_code=503, detail="GITHUB_TOKEN не настроен")
    _, sha = await github_get_blog()
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
            raise HTTPException(status_code=502, detail="Не удалось сохранить блог")
        _blog_cache["posts"] = posts
        _blog_cache["sha"] = r.json().get("content", {}).get("sha")
        _blog_cache["fetched_at"] = time.time()
        return True


# --- FastAPI ---
app = FastAPI(title="Monolog")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


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
        "prompts_loaded": {
            "layer_a": bool(LAYER_A),
            "layer_b": bool(LAYER_B),
            "layer_a_content": bool(LAYER_A_CONTENT),
        },
    }


@app.get("/providers")
async def providers_info():
    out = []
    for pid, cfg in PROVIDERS.items():
        out.append({
            "id": pid,
            "name": cfg["name"],
            "url": {
                "groq": "https://console.groq.com/keys",
                "openrouter": "https://openrouter.ai/keys",
                "cerebras": "https://cloud.cerebras.ai",
                "sambanova": "https://cloud.sambanova.ai",
            }.get(pid, ""),
            "models": list(cfg.get("all_models") or []),
        })
    return JSONResponse({"providers": out})


@app.post("/chat")
async def chat(request: Request):
    body = await request.json()
    user_message = (body.get("message") or "").strip()
    attachments = body.get("attachments") or []
    carried_metrics = body.get("carried_metrics") or {}

    if not user_message and not attachments:
        raise HTTPException(status_code=400, detail="Пустое сообщение")

    provider, base_url, model, api_key, source = pick_provider_and_model(
        body, user_message, carried_metrics
    )
    if not api_key:
        raise HTTPException(
            status_code=503,
            detail="Нет доступных ключей. Введите свой ключ в настройках.",
        )

    management_mode = (body.get("management_key") or "").strip() == MANAGEMENT_KEY
    log.info(
        f"Chat | provider={provider} | source={source} | model={model} | "
        f"management={management_mode}"
    )

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
            reply_text = "Извините, произошла ошибка обработки ответа. Попробуйте ещё раз."
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
        log.error(f"Chat error: {e}")
        fallback_metrics = merge_metrics({}, carried_metrics)
        fallback_metrics["protocol_integrity"] = False
        fallback_metrics["indicator_status"] = "warning"
        fallback_metrics["management_mode"] = management_mode
        return JSONResponse({
            "reply_text": "Извините, произошла ошибка. Попробуйте ещё раз.",
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


# --- Blog ---
@app.get("/blog")
async def blog_list():
    posts, _ = await github_get_blog()
    metas = []
    for p in posts:
        metas.append({
            "id": p.get("id"),
            "title": p.get("title"),
            "tags": p.get("tags", []),
            "author": p.get("author", "Автор"),
            "created_at": p.get("created_at"),
            "updated_at": p.get("updated_at"),
            "preview": (p.get("body") or "")[:180],
        })
    metas.sort(key=lambda x: x.get("created_at") or "", reverse=True)
    return JSONResponse({"posts": metas, "count": len(metas)})


@app.get("/blog/{post_id}")
async def blog_get(post_id: str):
    posts, _ = await github_get_blog()
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
    author = (body.get("author") or "Автор").strip()
    if not title or not text:
        raise HTTPException(status_code=400, detail="Нужны заголовок и текст")

    posts, _ = await github_get_blog()
    post_id = "post_" + str(int(time.time() * 1000))
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    new_post = {
        "id": post_id,
        "title": title,
        "body": text,
        "tags": tags if isinstance(tags, list) else [],
        "author": author,
        "created_at": now,
        "updated_at": now,
    }
    posts.append(new_post)
    await github_put_blog(posts, f"Blog: publish '{title[:50]}'")
    return JSONResponse({"ok": True, "id": post_id})


@app.delete("/blog/{post_id}")
async def blog_delete(post_id: str, request: Request):
    check_author(request)
    posts, _ = await github_get_blog()
    new_posts = [p for p in posts if p.get("id") != post_id]
    if len(new_posts) == len(posts):
        raise HTTPException(status_code=404, detail="Статья не найдена")
    await github_put_blog(new_posts, f"Blog: delete '{post_id}'")
    return JSONResponse({"ok": True})


# --- Code (ветка dev) ---
@app.get("/code/read")
async def code_read(request: Request, path: str):
    check_author(request)
    if not GITHUB_TOKEN:
        raise HTTPException(status_code=503, detail="GITHUB_TOKEN не настроен")
    url = f"{GITHUB_API}/repos/{GITHUB_REPO}/contents/{path}"
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {GITHUB_TOKEN}",
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get(url, headers=headers, params={"ref": CODE_BRANCH})
        branch_used = CODE_BRANCH
        if r.status_code == 404:
            r = await client.get(url, headers=headers, params={"ref": GITHUB_BRANCH})
            branch_used = GITHUB_BRANCH
        if r.status_code == 404:
            return JSONResponse({
                "exists": False, "path": path,
                "content": None, "sha": None, "branch": branch_used,
            })
        if r.status_code >= 400:
            raise HTTPException(status_code=502, detail="Не удалось прочитать файл")
        data = r.json()
        try:
            content = base64.b64decode(data.get("content", "")).decode("utf-8")
        except Exception:
            content = ""
        return JSONResponse({
            "exists": True, "path": path,
            "content": content, "sha": data.get("sha"), "branch": branch_used,
        })


@app.post("/code/save")
async def code_save(request: Request):
    check_author(request)
    if not GITHUB_TOKEN:
        raise HTTPException(status_code=503, detail="GITHUB_TOKEN не настроен")
    body = await request.json()
    path = (body.get("path") or "").strip()
    content = body.get("content") or ""
    message = (body.get("message") or f"Update {path}").strip()
    if not path:
        raise HTTPException(status_code=400, detail="Не указан путь")

    url = f"{GITHUB_API}/repos/{GITHUB_REPO}/contents/{path}"
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {GITHUB_TOKEN}",
    }
    sha = None
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get(url, headers=headers, params={"ref": CODE_BRANCH})
        if r.status_code == 200:
            sha = r.json().get("sha")
        content_b64 = base64.b64encode(content.encode("utf-8")).decode("utf-8")
        payload = {"message": message, "content": content_b64, "branch": CODE_BRANCH}
        if sha:
            payload["sha"] = sha
        r = await client.put(url, headers=headers, json=payload)
        if r.status_code >= 400:
            raise HTTPException(status_code=502, detail="Не удалось сохранить код")
        data = r.json()
        return JSONResponse({
            "ok": True, "path": path, "branch": CODE_BRANCH,
            "commit_sha": data.get("commit", {}).get("sha"),
            "html_url": data.get("commit", {}).get("html_url"),
        })


# --- Releases (архив) ---
@app.get("/releases")
async def releases_list():
    data, _ = await github_get_file(RELEASES_PATH)
    if not isinstance(data, list):
        data = []
    return JSONResponse({"releases": data})


@app.post("/releases/save")
async def releases_save(request: Request):
    check_author(request)
    if not GITHUB_TOKEN:
        raise HTTPException(status_code=503, detail="GITHUB_TOKEN не настроен")
    body = await request.json()
    releases = body.get("releases") or []
    if not isinstance(releases, list):
        raise HTTPException(status_code=400, detail="releases должен быть списком")
    await github_put_file(RELEASES_PATH, releases, "Update releases")
    return JSONResponse({"ok": True, "count": len(releases)})


# --- Управление (проверка ключа) ---
@app.post("/management/check")
async def management_check(request: Request):
    check_management(request)
    return JSONResponse({"ok": True, "management_mode": True})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=int(os.getenv("PORT", 8000)))