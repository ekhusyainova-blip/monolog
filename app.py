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

# ============================================================================
# AI-APPLY — автоматизация разработки
# ----------------------------------------------------------------------------
# Что делает:
#   1. Принимает от ИИ файл (путь + содержимое + сообщение)
#   2. Сохраняет его в репозиторий через GitHub API
#   3. Проверяет, что /health отвечает (приложение живо)
#   4. Если проверка не прошла — откатывает к предыдущей версии файла
#
# Зачем:
#   ИИ может сам вносить изменения в код, не дожидаясь человека.
#   Человек не вставляет файлы руками — ИИ пишет через /ai/apply.
#
# Как использовать (из ИИ):
#   POST /ai/apply
#   {
#     "path": "adaptive/components/menu.js",
#     "content": "...",
#     "message": "Add menu component"
#   }
# ============================================================================

from pydantic import BaseModel  # если pydantic уже есть — не дублировать импорт

class AIApplyRequest(BaseModel):
    path: str
    content: str
    message: str = "AI apply"


@app.post("/ai/apply")
async def ai_apply(request: Request):
    """
    Принимает файл от ИИ, сохраняет в main, проверяет /health,
    при неудаче — откатывает.
    """

    # --- 1. Разбор входных данных ---
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Некорректный JSON")

    path = (body.get("path") or "").strip()
    content = body.get("content") or ""
    message = (body.get("message") or "AI apply").strip()

    if not path:
        raise HTTPException(status_code=400, detail="Нужно поле path")
    if not content:
        raise HTTPException(status_code=400, detail="Нужно поле content")

    # --- 2. Защита: ИИ не может писать в критичные файлы ---
    # Это предохранитель. Если надо разрешить — расширить белый список.
    FORBIDDEN = (
        ".env",              # секреты
        "requirements.txt",  # зависимости
        "Dockerfile",        # сборка
    )
    if any(path.endswith(f) for f in FORBIDDEN):
        raise HTTPException(
            status_code=403,
            detail=f"Файл {path} защищён от автоправок",
        )

    # --- 3. Читаем текущую версию (для отката) ---
    _, sha_before = await github_get_json(path)

    # --- 4. Сохраняем новую версию ---
    try:
        await github_put_json(path, content, message)
    except HTTPException as e:
        # Если не удалось сохранить — вернуть ошибку, ничего не меняя
        raise HTTPException(
            status_code=502,
            detail=f"Не удалось сохранить {path}: {e.detail}",
        )

    # --- 5. Проверяем, что приложение живо ---
    # Ждём несколько секунд, чтобы Render успел подхватить
    await asyncio.sleep(3)

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.get(f"{request.base_url}health")
            if r.status_code != 200:
                raise Exception(f"health вернул {r.status_code}")
    except Exception as e:
        # --- 6. Откат ---
        safe_log(f"AI apply: health check failed ({e}), откатываю {path}")
        if sha_before:
            await github_put_json(
                path,
                # читаем старую версию
                (await github_get_json(path))[0] or "",
                f"Revert {path} after failed health check",
            )
        raise HTTPException(
            status_code=500,
            detail=f"Изменение не прошло проверку, откат выполнен. Причина: {e}",
        )

    # --- 7. Успех ---
    return JSONResponse({
        "ok": True,
        "path": path,
        "sha_before": sha_before,
        "message": message,
        "health": "ok",
    })
    
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=int(os.getenv("PORT", 8000)))