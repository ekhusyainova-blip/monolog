# core_backend/routers/debug_tools.py
# Полный набор диагностических эндпоинтов.
# APIRouter — подключается автоматически в full_app.py.

import os
import sys
import time
import importlib
import base64
import mimetypes

import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse, FileResponse

from core_backend.config import (
    GITHUB_TOKEN, GITHUB_REPO, GITHUB_BRANCH, GITHUB_API,
)


router = APIRouter(prefix="/debug", tags=["debug"])

_START_TIME = time.time()


def _gh_headers():
    h = {"Accept": "application/vnd.github+json"}
    if GITHUB_TOKEN:
        h["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    return h


# --- 1. MIME ---
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


# --- 2. Заголовки URL ---
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


# --- 3. Static check ---
@router.get("/static_check")
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


# --- 4. Env ---
@router.get("/env")
async def debug_env():
    safe_keys = ["APP_MODE", "GITHUB_BRANCH", "GITHUB_REPO", "CODE_BRANCH", "RENDER", "PORT"]
    return {k: os.environ.get(k) for k in safe_keys}


# --- 5. File info (что в GitHub) ---
@router.get("/file_info")
async def debug_file_info(path: str):
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


# --- 6. Файлы в контейнере ---
@router.get("/render_logs")
async def debug_render_logs():
    return {
        "python": sys.version,
        "platform": sys.platform,
        "cwd": os.getcwd(),
        "cwd_files": sorted(os.listdir(".")) if os.path.exists(".") else None,
        "core_backend_exists": os.path.exists("core_backend"),
        "core_backend_files": sorted(os.listdir("core_backend")) if os.path.exists("core_backend") else None,
        "routers_files": sorted(os.listdir("core_backend/routers")) if os.path.exists("core_backend/routers") else None,
        "mime_static_exists": os.path.exists("core_backend/mime_static.py"),
    }


# --- 7. Проверка mime_static ---
@router.get("/check_mime_static")
async def debug_check_mime_static():
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
        result["full_app_uses_only_StaticFiles"] = ("StaticFiles" in src and "MimeStaticFiles" not in src)
    except Exception as e:
        result["full_app_error"] = str(e)

    return JSONResponse(result)


# --- 8. Кэш ---
@router.get("/cache_info")
async def debug_cache_info(url: str):
    if not url.startswith("http"):
        url = "https://ai-monolog.onrender.com" + url
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            r = await client.get(url)
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"GET не прошёл: {e}")
    keys = ["etag", "age", "cache-control", "cf-cache-status", "last-modified", "date", "expires"]
    return JSONResponse({
        "url": url,
        "cache_headers": {k: r.headers.get(k) for k in keys},
        "content_type": r.headers.get("content-type"),
    })


# --- 9. Deploy info ---
@router.get("/deploy_info")
async def debug_deploy_info():
    return {
        "uptime_seconds": round(time.time() - _START_TIME, 1),
        "cwd": os.getcwd(),
        "app_mode": os.environ.get("APP_MODE"),
        "render": os.environ.get("RENDER"),
        "render_service_id": os.environ.get("RENDER_SERVICE_ID"),
        "render_instance_id": os.environ.get("RENDER_INSTANCE_ID"),
        "render_external_url": os.environ.get("RENDER_EXTERNAL_URL"),
        "commit": os.environ.get("RENDER_GIT_COMMIT"),
        "branch": os.environ.get("RENDER_GIT_BRANCH"),
        "repo": os.environ.get("RENDER_GIT_REPO_SLUG"),
    }


# --- 10. index.html ---
@router.get("/index_html")
async def debug_index_html():
    if not os.path.exists("index.html"):
        return JSONResponse({"exists": False})
    with open("index.html", "r", encoding="utf-8") as f:
        content = f.read()
    return JSONResponse({
        "exists": True,
        "size": len(content),
        "content": content,
    })