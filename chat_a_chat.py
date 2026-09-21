# chat_a_chat.py
# Тема: chat
# Слой: A (данные, точка входа, шина, app, роуты)

import os
import time
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware

# A · данные
PROVIDERS = {
    "groq": {
        "url": "https://api.groq.com/openai/v1/chat/completions",
        "model": "openai/gpt-oss-120b",
        "env_keys": "GROQ_API_KEYS",
    },
    "cerebras": {
        "url": "https://api.cerebras.ai/v1/chat/completions",
        "model": "gpt-oss-120b",
        "env_keys": "CEREBRAS_API_KEY",
    },
    "sambanova": {
        "url": "https://api.sambanova.ai/v1/chat/completions",
        "model": "Meta-Llama-3.3-70B-Instruct",
        "env_keys": "SAMBANOVA_API_KEY",
    },
    "openrouter": {
        "url": "https://openrouter.ai/api/v1/chat/completions",
        "model": "nvidia/nemotron-3-ultra",
        "env_keys": "OPENROUTER_API_KEY",
    },
}

SETTINGS = {
    "temperature": 0.7,
    "max_tokens": 2048,
    "timeout": 120,
    "provider_order": ["groq", "cerebras", "sambanova", "openrouter"],
    "cooldown_sec": 65,
}

def load_keys(env_name: str) -> list:
    raw = os.getenv(env_name, "").strip()
    if not raw:
        return []
    return [k.strip() for k in raw.split(",") if k.strip()]

KEYS = {
    "groq": load_keys("GROQ_API_KEYS"),
    "cerebras": load_keys("CEREBRAS_API_KEY"),
    "sambanova": load_keys("SAMBANOVA_API_KEY"),
    "openrouter": load_keys("OPENROUTER_API_KEY"),
}

PROMPTS = {
    "layer_a": "Ты — Monolog.",
    "layer_b": "Ты — Monolog.",
    "layer_c": "Ты — Monolog.",
    "layer_d": "Ты — Monolog.",
    "layer_a_content": "Ты — Monolog.",
}

# A · путь к странице чата
BASE_DIR = Path(__file__).resolve().parent
UI_PATH = BASE_DIR / "chat_a_page.html"

def read_ui() -> str:
    try:
        return UI_PATH.read_text(encoding="utf-8")
    except Exception as e:
        print(f"[chat_a_chat] UI read error: {e}", flush=True)
        return "<!DOCTYPE html><html><body><h1>Monolog</h1><p>UI не найден.</p></body></html>"

# A · шина
HANDLERS = {}
EVENTS = []

def on(event_name: str):
    def wrapper(fn):
        HANDLERS.setdefault(event_name, []).append(fn)
        return fn
    return wrapper

def emit(event_name: str, payload: dict):
    for fn in HANDLERS.get(event_name, []):
        fn(payload)

# A · app и роуты
app = FastAPI(title="Monolog Chat")
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health():
    return {
        "ok": True,
        "status": "alive",
        "providers": {name: len(KEYS.get(name, [])) for name in PROVIDERS},
    }

@app.post("/chat")
async def chat(request: Request):
    body = await request.json()
    event = {
        "text": (body.get("text") or "").strip(),
        "context": body.get("context"),
        "provider": body.get("provider"),
    }
    if not event["text"]:
        return JSONResponse(
            {"ok": False, "error": {"code": 400, "class": "validation", "message": "Пустой текст"}},
            status_code=400,
        )
    EVENTS.clear()
    emit("user_message", event)
    if not EVENTS:
        return JSONResponse(
            {"ok": False, "error": {"code": 500, "class": "internal", "message": "Нет ответа от цепочки"}},
            status_code=500,
        )
    return JSONResponse(EVENTS[-1])

@app.get("/", response_class=HTMLResponse)
async def index():
    return read_ui()

# A · импорт B в конце
import chat_b_chat