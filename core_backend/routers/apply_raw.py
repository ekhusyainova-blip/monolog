# core_backend/routers/apply_raw.py
# Эндпоинт /ai/apply_raw — принимает text/plain body.
# path и message — в query-параметрах.
# Используется для заливки многострочных файлов без JSON-лома.

import asyncio

import httpx
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse

from core_backend.github_api import github_get_sha, github_put_file


router = APIRouter(tags=["code"])


@router.post("/ai/apply_raw")
async def ai_apply_raw(request: Request, path: str, message: str = "AI apply raw"):
    """
    Принимает сырой текст (не JSON).
    path и message — в query-параметрах URL.
    """
    raw = await request.body()
    try:
        content = raw.decode("utf-8")
    except Exception:
        raise HTTPException(status_code=400, detail="Тело должно быть UTF-8 текстом")

    path = path.strip()
    if not path:
        raise HTTPException(status_code=400, detail="Нужно поле path в query")
    if not content:
        raise HTTPException(status_code=400, detail="Пустое тело")

    FORBIDDEN = (".env", "requirements.txt", "Dockerfile")
    if any(path.endswith(f) for f in FORBIDDEN):
        raise HTTPException(status_code=403, detail=f"Файл {path} защищён от автоправок")

    sha_before = await github_get_sha(path)
    await github_put_file(path, content, message)

    # Проверяем, что приложение живо
    await asyncio.sleep(3)

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.get("https://ai-monolog.onrender.com/health")
            if r.status_code != 200:
                raise Exception(f"health вернул {r.status_code}")
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Health check не прошёл: {e}",
        )

    return JSONResponse({
        "ok": True,
        "path": path,
        "sha_before": sha_before,
        "message": message,
        "health": "ok",
    })