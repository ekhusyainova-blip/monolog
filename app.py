# app.py
# Точка входа Monolog.
# Статика, CORS, автосканирование роутеров из core_backend/routers/.

import pkgutil
import importlib

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from core_backend.config import (
    CORS_ORIGINS,
    PROVIDERS,
    _DEV_KEYS_GROQ,
    ALLOW_BYOK,
    AUTHOR_SECRET,
    MANAGEMENT_KEY,
    GITHUB_TOKEN,
    MAX_MESSAGE_LEN,
    SOFT_MESSAGE_LEN,
    MAX_TOKENS,
    META_MAX_TOKENS,
    LAYER_A,
    LAYER_B,
    LAYER_A_CONTENT,
)


app = FastAPI(title="Monolog")


# --- статика ---
app.mount("/core", StaticFiles(directory="core"), name="core")
app.mount("/adaptive", StaticFiles(directory="adaptive"), name="adaptive")
app.mount("/blog", StaticFiles(directory="blog"), name="blog")


# --- CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


# --- автосканирование роутеров из core_backend/routers/ ---
import core_backend.routers as _routers_pkg

for _, module_name, _ in pkgutil.iter_modules(_routers_pkg.__path__):
    if module_name.startswith("_"):
        continue
    module = importlib.import_module(f"core_backend.routers.{module_name}")
    if hasattr(module, "router"):
        app.include_router(module.router)


# --- базовые эндпоинты ---
@app.get("/")
async def root():
    return FileResponse("index.html")


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "version": "2.4",
        "dev_keys": len(_DEV_KEYS_GROQ),
        "byok": ALLOW_BYOK,
        "github_ready": bool(GITHUB_TOKEN),
        "author_secret_set": bool(AUTHOR_SECRET),
        "management_key_set": bool(MANAGEMENT_KEY),
        "providers": list(PROVIDERS.keys()),
        "cors": CORS_ORIGINS,
        "limits": {
            "max_message_len": MAX_MESSAGE_LEN,
            "soft_message_len": SOFT_MESSAGE_LEN,
            "max_tokens": MAX_TOKENS,
            "meta_max_tokens": META_MAX_TOKENS,
        },
        "prompts_loaded": {
            "layer_a": bool(LAYER_A),
            "layer_b": bool(LAYER_B),
            "layer_a_content": bool(LAYER_A_CONTENT),
        },
    }


@app.get("/providers")
async def providers_info():
    urls = {
        "groq": "https://console.groq.com/keys",
        "openrouter": "https://openrouter.ai/keys",
        "cerebras": "https://cloud.cerebras.ai",
        "sambanova": "https://cloud.sambanova.ai",
    }
    out = []
    for pid, cfg in PROVIDERS.items():
        out.append({
            "id": pid,
            "name": cfg["name"],
            "url": urls.get(pid, ""),
            "models": list(cfg.get("all_models") or []),
        })
    return JSONResponse({"providers": out})


if __name__ == "__main__":
    import uvicorn
    import os
    uvicorn.run("app:app", host="0.0.0.0", port=int(os.getenv("PORT", 8000)))