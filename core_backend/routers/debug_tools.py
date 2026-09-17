# core_backend/routers/debug_tools.py
# Диагностические эндпоинты: MIME, заголовки, состояние StaticFiles.
# APIRouter — подключается автоматически в full_app.py.

import mimetypes

import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse


router = APIRouter(prefix="/debug", tags=["debug"])


@router.get("/mime")
async def debug_mime():
    """Что Python знает о MIME-типах. Проверка .js, .css, .json."""
    return {
        "js": mimetypes.guess_type("test.js"),
        "css": mimetypes.guess_type("test.css"),
        "json": mimetypes.guess_type("test.json"),
        "html": mimetypes.guess_type("test.html"),
        "svg": mimetypes.guess_type("test.svg"),
        "loaded_mime_types_file": getattr(mimetypes, "inited", None),
        "known_types_count": len(mimetypes.types_map) if hasattr(mimetypes, "types_map") else None,
    }


@router.get("/headers")
async def debug_headers(url: str):
    """
    Делает HEAD-запрос к URL на том же хосте и возвращает заголовки.
    Пример: /debug/headers?url=/core/core.js
    """
    if not url.startswith("http"):
        url = "https://ai-monolog.onrender.com" + url

    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            r = await client.head(url)
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"HEAD не прошёл: {e}")

    return JSONResponse({
        "url": url,
        "status": r.status_code,
        "headers": dict(r.headers),
    })


@router.get("/static_check")
async def debug_static_check(path: str):
    """
    Проверяет, что отдаёт StaticFiles для указанного пути.
    Пример: /debug/static_check?path=core/core.js
    """
    # Проверяем два варианта: /core/core.js и /core/core.js
    if path.startswith("/"):
        path_clean = path[1:]
    else:
        path_clean = path

    # Основной вариант через URL
    url = "https://ai-monolog.onrender.com/" + path_clean

    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            r = await client.get(url)
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"GET не прошёл: {e}")

    body = r.content[:200]

    return JSONResponse({
        "path": path_clean,
        "url": url,
        "status": r.status_code,
        "content_type": r.headers.get("content-type"),
        "content_length": len(r.content),
        "first_200_bytes": body.decode("utf-8", errors="replace"),
    })


@router.get("/env")
async def debug_env():
    """Что видит backend из env (без секретов)."""
    import os
    safe_keys = [
        "APP_MODE", "GITHUB_BRANCH", "GITHUB_REPO", "CODE_BRANCH",
        "PYTHON_VERSION", "RENDER", "PORT",
    ]
    return {
        k: ("<set>" if k in os.environ and "SECRET" in k.upper() or "TOKEN" in k.upper() or "KEY" in k.upper() else os.environ.get(k))
        for k in safe_keys
    }