# core_backend/routers/debug_tools.py
# Диагностика: MIME, заголовки, состояние StaticFiles, состояние файлов в GitHub.
# APIRouter — подключается автоматически в full_app.py.

import os
import mimetypes
import importlib
import base64

import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from core_backend.config import (
    GITHUB_TOKEN, GITHUB_REPO, GITHUB_BRANCH, GITHUB_API,
)


router = APIRouter(prefix="/debug", tags=["debug"])


def _gh_headers():
    h = {"Accept": "application/vnd.github+json"}
    if GITHUB_TOKEN:
        h["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    return h


@router.get("/mime")
async def debug_mime():
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


")
async def debug_static_check(path: str):
    path_clean = path[1:] if path.startswith("/") else path
    url = "https://ai-monolog.onrender.com/" + path_clean
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            r = await client.get(url)
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"GET не прошёл: {e}")
    return JSONResponse({
        "path": path_clean,
        "url": url,
        "status": r.status_code,
        "content_type": r.headers.get("content-type"),
        "content_length": len(r.content),
        "first_200_bytes": r.content[:200].decode("utf-8", errors="replace"),
    })


@router.get("/env")
async def debug_env():
    safe_keys = ["APP_MODE", "GITHUB_BRANCH", "GITHUB_REPO", "CODE_BRANCH", "RENDER", "PORT"]
    return {k: os.environ.get(k) for k in safe_keys}


# --- НОВОЕ: file_info, render_logs, check_mime_static ---

@router.get("/file_info")
async def debug_file_info(path: str):
    """Проверяет, что лежит в GitHub по указанному path."""
    url = f"{GITHUB_API}/repos/{GITHUB_REPO}/contents/{path}"
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get(url, headers=_gh_headers(), params={"ref": GITHUB_BRANCH})
        if r.status_code == 404:
            return JSONResponse({"exists": False, "path": path})
        if r.status_code >= 400:
            raise HTTPException(status_code=502, detail=f"GitHub: {r.status_code}")
        data = r.json()
        try:
            raw = base64.b64decode(data.get("content", "")).decode("utf-8")
        except Exception:
            raw = ""
        return JSONResponse({
            "exists": True,
            "path": path,
            "size": data.get("size"),
            "sha": data.get("sha"),
            "contains_mime_static": "MimeStaticFiles" in raw,
            "contains_static_files": "StaticFiles" in raw,
            "first_300": raw[:300],
        })


@router.get("/render_logs")
async def debug_render_logs():
    """Не может читать реальные Render Logs — но отдаёт ключевые маркеры."""
    import sys
    return {
        "python": sys.version,
        "platform": sys.platform,
        "cwd": os.getcwd(),
        "cwd_files": os.listdir(".") if os.path.exists(".") else None,
        "core_backend_exists": os.path.exists("core_backend"),
        "core_backend_files": os.listdir("core_backend") if os.path.exists("core_backend") else None,
        "routers_files": os.listdir("core_backend/routers") if os.path.exists("core_backend/routers") else None,
        "mime_static_exists": os.path.exists("core_backend/mime_static.py"),
    }


@router.get("/check_mime_static")
async def debug_check_mime_static():
    """Проверяет, что mime_static импортируется и используется."""
    result = {}
    try:
        mod = importlib.import_module("core_backend.mime_static")
        result["import_ok"] = True
        result["has_MimeStaticFiles"] = hasattr(mod, "MimeStaticFiles")
        result["has_guess_mime"] = hasattr(mod, "guess_mime")
        if hasattr(mod, "guess_mime"):
            result["test_js"] = mod.guess_mime("test.js")
            result["test_css"] = mod.guess_mime("test.css")
    except Exception as e:
        result["import_ok"] = False
        result["error"] = str(e)

    try:
        full = importlib.import_module("core_backend.full_app")
        src = open(full.__file__, "r", encoding="utf-8").read() if full.__file__ else ""
        result["full_app_uses_MimeStaticFiles"] = "MimeStaticFiles" in src
        result["full_app_uses_StaticFiles"] = "StaticFiles" in src and "MimeStaticFiles" not in src
    except Exception as e:
        result["full_app_error"] = str(e)

    return JSONResponse(result)