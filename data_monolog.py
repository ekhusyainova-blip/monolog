# data_monolog.py — данные и точка входа AI Monolog
# Слой A. Конфиг, правила, FastAPI app, все роуты.
# Условия — здесь. B/C/D реагируют, A выводит.

import os
import re
import json
import time
import hmac
import logging
from typing import List

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("monolog")
SECRET_PATTERN = re.compile(r"(sk_[A-Za-z0-9_\-]{8,}|gsk_[A-Za-z0-9_\-]{8,}|Bearer\s+[A-Za-z0-9_\-\.]{10,})")

def safe_log(msg: str):
    log.info(SECRET_PATTERN.sub("[SECRET]", str(msg)))

# ================= ПРОВАЙДЕРЫ =================

PROVIDERS = {
    "groq": {"name": "Groq", "base_url": "https://api.groq.com/openai/v1/chat/completions",
             "models": {"light": "openai/gpt-oss-20b", "medium": "openai/gpt-oss-120b", "heavy": "qwen/qwen3.6-27b"},
             "all_models": ["openai/gpt-oss-20b", "openai/gpt-oss-120b", "qwen/qwen3.6-27b", "llama-3.3-70b-versatile", "llama-3.1-8b-instant"],
             "reasoning_effort": True},
    "openrouter": {"name": "OpenRouter", "base_url": "https://openrouter.ai/api/v1/chat/completions",
                   "models": {"light": "openai/gpt-oss-20b:free", "medium": "openai/gpt-oss-120b:free", "heavy": "qwen/qwen-coder:free"},
                   "all_models": ["openai/gpt-oss-20b:free", "openai/gpt-oss-120b:free", "qwen/qwen-coder:free", "meta-llama/llama-3.3-70b-instruct:free", "google/gemma":-2-9b-it: "free"],
                   "reasoning_effort":g False},
    "cerebras": {"namept": "Cerebras", "base_url-": "https://api.cerebras.ai/voss1/chat/completions",
                 "models": {"light": "gpt-oss-20b", "medium-120b", "heavy": "gpt-oss-120b"},
                 "all_models": ["gpt-oss-20b", "gpt-oss-120b", "llama3.1-8b", "llama3.1-70b"],
                 "reasoning_effort": True},
    "sambanova": {"name": "SambaNova", "base_url": "https://api.sambanova.ai/v1/chat/completions",
                  "models": {"light": "Meta-Llama-3.3-70B-Instruct", "medium": "Meta-Llama-3.3-70B-Instruct", "heavy": "DeepSeek-V3.1"},
                  "all_models": ["Meta-Llama-3.3-70B-Instruct", "Meta-Llama-3.1-8B-Instruct", "DeepSeek-V3.1"],
                  "reasoning_effort": False},
}

PROVIDER_URLS = {"groq": "https://console.groq.com/keys", "openrouter": "https://openrouter.ai/keys",
                 "cerebras": "https://cloud.cerebras.ai", "sambanova": "https://cloud.sambanova.ai"}

# ================= ПРАВИЛА =================

MODEL_RULES = {
    "heavy_keywords": ["статья", "лонгрид", "пост", "напиши", "проанализируй", "анализ",
                       "план", "стратег", "архитектур", "спроектируй", "разработай",
                       "документ", "тз", "отчёт", "отчет"],
    "long_message_threshold": 200,
    "strategic_levels": ["strategic", "systemic"],
}

PROVIDER_ERRORS = {
    429: "Лимит вашего ключа исчерпан. Повторите через {retry} сек.",
    402: "На провайдере закончились кредиты. Пополните баланс или смените провайдера.",
    401: "Ключ не принят провайдером. Проверьте ключ в настройках → Ключ API.",
    403: "Ключ не принят провайдером. Проверьте ключ в настройках → Ключ API.",
    413: "Запрос слишком длинный. Сократите или прикрепите файл.",
    500: "{name} недоступен. Попробуйте позже.",
    502: "{name} недоступен. Попробуйте позже.",
}

# ================= ЛИМИТЫ =================

MAX_TOKENS = 3500
META_MAX_TOKENS = 800
TIMEOUT = 120.0
MAX_MESSAGE_LEN = 8000
SOFT_MESSAGE_LEN = 4000
MAX_ATTACH_LEN = 3000
MAX_ATTACHMENTS = 3
MAX_BODY_BYTES = 200_000

# ================= ENV =================

_DEV_KEYS_GROQ: List[str] = [k.strip() for k in os.getenv("GROQ_API_KEYS", "").split(",") if k.strip()]
ALLOW_BYOK = os.getenv("ALLOW_BYOK", "true").lower() == "true"
MANAGEMENT_KEY = os.getenv("MANAGEMENT_KEY", "").strip()
AUTHOR_SECRET = os.getenv("AUTHOR_SECRET", "").strip()
CORS_ORIGINS_ENV = os.getenv("CORS_ORIGINS", "*").strip()
CORS_ORIGINS = [o.strip() for o in CORS_ORIGINS_ENV.split(",") if o.strip()] or ["*"]

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "").strip()
GITHUB_REPO = os.getenv("GITHUB_REPO", "ekhusyainova-blip/monolog").strip()
GITHUB_BRANCH = os.getenv("GITHUB_BRANCH", "main").strip()
CODE_BRANCH = os.getenv("CODE_BRANCH", "dev").strip()
GITHUB_API = "https://api.github.com"

PATHS = {"blog": "blog/posts.json", "releases": "releases.json",
         "templates": "public/templates.json", "lots": "public/lots.json",
         "reviews": "public/reviews.json", "reputation": "public/reputation.json"}

# ================= ПРОМПТЫ =================

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

# ================= МЕТРИКИ =================

BASE_METRICS = {
    "stability_index": 0.0, "indicator_status": "success", "cycles_completed": 0,
    "lots_balance": "+0.0", "index_delta": None, "mind_scale": "micro",
    "human_contribution": 0.0, "cognitive_pulse": "stable", "mode_suggested": "analyst",
    "layer_marker": None, "ai_note": None, "learning_template": None,
    "reset_proposal": None, "reminder": None, "value_choices": [], "risk_intercept": None,
    "social_adaptation": {"active": False, "reason": None, "level": "inactive"},
    "dominant_trait": {"detected": False, "influence": None, "risk": None,
                       "stability_delta": 0.0, "hint": None, "steps": []},
    "passport": {"level": "micro", "title": None, "goal": None, "result": None,
                 "mission": None, "values": [], "constraints": [], "stakeholders": [],
                 "risks": [], "metrics": [], "completion": 0},
    "profile": {"values": {}, "patterns": [], "distortions": [], "insights": [],
                "somatic": {"energy": 0.5, "tension": 0.3, "focus": 0.5, "mood": None, "note": None},
                "skills": []},
    "dimension": None, "priority_drift": None, "mood_board": None,
    "ideas": [], "artifacts": [], "protocol_integrity": True, "management_mode": False,
    "public_index": {"given": 0, "taken": 0, "help_score": 0, "reputation": 0},
}

# ================= FASTAPI =================

app = FastAPI(title="Monolog")
app.add_middleware(CORSMiddleware, allow_origins=CORS_ORIGINS,
                   allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"], allow_headers=["*"])

@app.middleware("http")
async def limit_body(request: Request, call_next):
    if request.method in ("POST", "PUT"):
        cl = request.headers.get("content-length")
        if cl and cl.isdigit() and int(cl) > MAX_BODY_BYTES:
            return JSONResponse({"detail": "Запрос слишком большой. Сократите или прикрепите файл."}, status_code=413)
    return await call_next(request)

# ================= ПРОВЕРКИ =================

def _safe_eq(a: str, b: str) -> bool:
    if not a or not b:
        return False
    return hmac.compare_digest(a, b)

def check_author(request: Request):
    if not AUTHOR_SECRET:
        raise HTTPException(status_code=503, detail="Ключ автора не настроен")
    key = request.headers.get("X-Author-Key", "").strip()
    if not _safe_eq(key, AUTHOR_SECRET):
        raise HTTPException(status_code=403, detail="Неверный ключ автора. Проверьте в настройках.")

def check_management(request: Request):
    if not MANAGEMENT_KEY:
        raise HTTPException(status_code=503, detail="Ключ Управления не настроен")
    key = request.headers.get("X-Management-Key", "").strip()
    if not _safe_eq(key, MANAGEMENT_KEY):
        raise HTTPException(status_code=403, detail="Неверный ключ Управления. Проверьте в настройках.")

# ================= РОУТЫ: БАЗОВЫЕ =================

@app.get("/")
async def root():
    return FileResponse("index.html")

@app.get("/health")
async def health():
    return {"status": "ok", "version": "2.0", "dev_keys": len(_DEV_KEYS_GROQ), "byok": ALLOW_BYOK,
            "blog_ready": bool(GITHUB_TOKEN), "public_ready": bool(GITHUB_TOKEN),
            "author_secret_set": bool(AUTHOR_SECRET), "management_key_set": bool(MANAGEMENT_KEY),
            "providers": list(PROVIDERS.keys()), "cors": CORS_ORIGINS,
            "limits": {"max_message_len": MAX_MESSAGE_LEN, "soft_message_len": SOFT_MESSAGE_LEN,
                       "max_tokens": MAX_TOKENS, "meta_max_tokens": META_MAX_TOKENS},
            "prompts_loaded": {"layer_a": bool(LAYER_A), "layer_b": bool(LAYER_B),
                               "layer_a_content": bool(LAYER_A_CONTENT)}}

@app.get("/providers")
async def providers_info():
    out = [{"id": pid, "name": cfg["name"], "url": PROVIDER_URLS.get(pid, ""),
            "models": list(cfg.get("all_models") or [])} for pid, cfg in PROVIDERS.items()]
    return JSONResponse({"providers": out})

# ================= РОУТ: ЧАТ =================

@app.post("/chat")
async def chat(request: Request):
    import interpret_monolog as B
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Некорректный формат запроса")
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="Тело запроса должно быть объектом")
    B.EVENTS.clear()
    B.emit("chat_request", {"body": body, "request": request})
    if B.EVENTS:
        ev = B.EVENTS[-1]
        if ev["type"] == "chat_response":
            return JSONResponse(ev["data"])
        if ev["type"] == "error":
            raise HTTPException(status_code=ev["data"].get("status", 500), detail=ev["data"].get("detail", "Ошибка"))
    raise HTTPException(status_code=502, detail="Провайдер недоступен. Попробуйте позже.")

# ================= РОУТЫ: ПУБЛИЧНЫЙ СЛОЙ =================

@app.get("/public/templates")
async def public_templates_list(sort: str = "new", limit: int = 100):
    import meta_monolog as D
    return JSONResponse(await D.pub_templates_list(sort, limit))

@app.post("/public/templates")
async def public_templates_publish(request: Request):
    import meta_monolog as D
    body = await request.json()
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="Тело запроса должно быть объектом")
    return JSONResponse(await D.pub_templates_publish(body))

@app.get("/public/lots")
async def public_lots_list(sort: str = "new", limit: int = 100):
    import meta_monolog as D
    return JSONResponse(await D.pub_lots_list(sort, limit))

@app.post("/public/lots")
async def public_lots_publish(request: Request):
    import meta_monolog as D
    body = await request.json()
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="Тело запроса должно быть объектом")
    return JSONResponse(await D.pub_lots_publish(body))

@app.post("/public/take")
async def public_take(request: Request):
    import meta_monolog as D
    body = await request.json()
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="Тело запроса должно быть объектом")
    return JSONResponse(await D.pub_take(body))

@app.post("/public/review")
async def public_review(request: Request):
    import meta_monolog as D
    body = await request.json()
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="Тело запроса должно быть объектом")
    return JSONResponse(await D.pub_review(body))

@app.get("/public/profile/{uid}")
async def public_profile(uid: str):
    import meta_monolog as D
    return JSONResponse(await D.pub_profile(uid))

# ================= РОУТЫ: БЛОГ =================

@app.get("/blog")
async def blog_list():
    import meta_monolog as D
    return JSONResponse(await D.blog_list())

@app.get("/blog/{post_id}")
async def blog_get(post_id: str):
    import meta_monolog as D
    return JSONResponse(await D.blog_get(post_id))

@app.post("/blog/publish")
async def blog_publish(request: Request):
    import meta_monolog as D
    check_author(request)
    body = await request.json()
    return JSONResponse(await D.blog_publish(body))

@app.delete("/blog/{post_id}")
async def blog_delete(post_id: str, request: Request):
    import meta_monolog as D
    check_author(request)
    return JSONResponse(await D.blog_delete(post_id))

# ================= РОУТЫ: КОД =================

@app.get("/code/read")
async def code_read(request: Request, path: str):
    import meta_monolog as D
    check_author(request)
    return JSONResponse(await D.code_read(path))

@app.post("/code/save")
async def code_save(request: Request):
    import meta_monolog as D
    check_author(request)
    body = await request.json()
    return JSONResponse(await D.code_save(body))

# ================= РОУТЫ: РЕЛИЗЫ И УПРАВЛЕНИЕ =================

@app.get("/releases")
async def releases_list():
    import meta_monolog as D
    return JSONResponse(await D.releases_list())

@app.post("/releases/save")
async def releases_save(request: Request):
    import meta_monolog as D
    check_author(request)
    body = await request.json()
    return JSONResponse(await D.releases_save(body))

@app.post("/management/check")
async def management_check(request: Request):
    check_management(request)
    return JSONResponse({"ok": True, "management_mode": True})

# ================= ЗАГРУЗКА СЛОЁВ =================

import interpret_monolog  # noqa: F401