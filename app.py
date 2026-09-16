# app.py — точка входа Monolog.
# Только импорты и подключение роутеров. Логика — в core/ и adaptive/.

import os
import logging
import re

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("monolog")

SECRET_PATTERN = re.compile(r"(sk_[A-Za-z0-9_\-]{8,}|gsk_[A-Za-z0-9_\-]{8,}|Bearer\s+[A-Za-z0-9_\-\.]{10,})")

def safe_log(msg: str):
    log.info(SECRET_PATTERN.sub("[SECRET]", str(msg)))


MAX_BODY_BYTES = 200_000
CORS_ORIGINS_ENV = os.getenv("CORS_ORIGINS", "*").strip()
CORS_ORIGINS = [o.strip() for o in CORS_ORIGINS_ENV.split(",") if o.strip()] or ["*"]


app = FastAPI(title="Monolog")

app.mount("/core", StaticFiles(directory="core"), name="core")
app.mount("/adaptive", StaticFiles(directory="adaptive"), name="adaptive")
app.mount("/public", StaticFiles(directory="public"), name="public")
app.mount("/blog", StaticFiles(directory="blog"), name="blog")

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


@app.middleware("http")
async def limit_body(request: Request, call_next):
    if request.method in ("POST", "PUT"):
        cl = request.headers.get("content-length")
        if cl and cl.isdigit() and int(cl) > MAX_BODY_BYTES:
            return JSONResponse({"detail": "Запрос слишком большой. Сократите или прикрепите файл."}, status_code=413)
    return await call_next(request)


@app.get("/")
async def root():
    return FileResponse("index.html")


# --- Подключение роутеров ---
from core.app_core import router as core_router
from adaptive.app_public import router as public_router
from adaptive.app_code import router as code_router
from adaptive.app_patches import router as patches_router

app.include_router(core_router)
app.include_router(public_router)
app.include_router(code_router)
app.include_router(patches_router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=int(os.getenv("PORT", 8000)))