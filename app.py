# app.py
# Точка входа Monolog. Подключает модули из core_backend/.

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

from core_backend.chat import router as chat_router
from core_backend.public_templates import router as public_tpl_router
from core_backend.public_lots import router as public_lots_router
from core_backend.code_ai import router as code_router


app = FastAPI(title="Monolog")

# --- статика ---
app.mount("/core", StaticFiles(directory="core"), name="core")
app.mount("/adaptive", StaticFiles(directory="adaptive"), name="adaptive")
app.mount("/public", StaticFiles(directory="public"), name="public")
app.mount("/blog", StaticFiles(directory="blog"), name="blog")

# --- CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# --- роутеры ---
app.include_router(chat_router)
app.include_router(public_tpl_router)
app.include_router(public_lots_router)
app.include_router(code_router)


@app.get("/")
async def root():
    return FileResponse("index.html")


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "version": "2.3",
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