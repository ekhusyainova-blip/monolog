# app.py — точка входа Monolog.
# Безопасный режим: если роутер не найден, приложение всё равно стартует.

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

# Статика — только те папки, что точно есть
for _dir, _name in (("core", "core"), ("adaptive", "adaptive"), ("public", "public"), ("blog", "blog")):
    if os.path.isdir(_dir):
        app.mount(f"/{_name}", StaticFiles(directory=_dir), name=_name)
    else:
        log.warning(f"Static dir not found: {_dir}")

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


# --- Роутеры (мягкое подключение) ---
def _try_include(module_path: str, router_name: str = "router"):
    try:
        mod = __import__(module_path, fromlist=[router_name])
        r = getattr(mod, router_name)
        app.include_router(r)
        log.info(f"[router] подключён: {module_path}")
    except Exception as e:
        log.warning(f"[router] не подключён {module_path}: {e}")


_try_include("core.chat")
_try_include("adaptive.public")
_try_include("adaptive.code")
_try_include("adaptive.patches")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=int(os.getenv("PORT", 8000)))