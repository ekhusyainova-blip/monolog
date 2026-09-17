# core_backend/routers/debug_server.py
# Диагностика сервера: MIME, заголовки, кэш, env, deploy, python.
# APIRouter — подключается автоматически.

import os
import sys
import time
import importlib
import mimetypes

import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse


router = APIRouter(prefix="/debug/server", tags=["debug-server"])

_START_TIME = time.time()


@router.get("/mime")
async def mime():
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
async def headers(url: str):
    if not url.startswith("http"):
        url = "https://ai-monolog.onrender.com" + url
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            r = await client.head(url)
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"HEAD: {e}")
    return JSONResponse({"url": url, "status": r.status_code, "headers": dict(r.headers)})


@router.get("/static_check")
async def static_check(path: str):
    p = path[1:] if path.startswith("/") else path
    url = "https://ai-monolog.onrender.com/" + p
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            r = await client.get(url)
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"GET: {e}")
    return JSONResponse({
        "path": p, "url": url, "status": r.status_code,
        "content_type": r.headers.get("content-type"),
        "content_length": len(r.content),
        "first_200_bytes": r.content[:200].decode("utf-8", errors="replace"),
    })


@router.get("/env")
async def env():
    keys = ["APP_MODE", "GITHUB_BRANCH", "GITHUB_REPO", "CODE_BRANCH",
            "RENDER", "PORT", "PYTHON_VERSION"]
    return {k: os.environ.get(k) for k in keys}


@router.get("/deploy_info")
async def deploy_info():
    return {
        "uptime_seconds": round(time.time() - _START_TIME, 1),
        "cwd": os.getcwd(),
        "app_mode": os.environ.get("APP_MODE"),
        "commit": os.environ.get("RENDER_GIT_COMMIT"),
        "branch": os.environ.get("RENDER_GIT_BRANCH"),
        "repo": os.environ.get("RENDER_GIT_REPO_SLUG"),
        "instance_id": os.environ.get("RENDER_INSTANCE_ID"),
    }


@router.get("/cache_info")
async def cache_info(url: str):
    if not url.startswith("http"):
        url = "https://ai-monolog.onrender.com" + url
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            r = await client.get(url)
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"GET: {e}")
    keys = ["etag", "age", "cache-control", "cf-cache-status",
            "last-modified", "date", "expires"]
    return JSONResponse({
        "url": url,
        "cache_headers": {k: r.headers.get(k) for k in keys},
        "content_type": r.headers.get("content-type"),
    })


@router.get("/python_info")
async def python_info():
    info = {
        "python": sys.version,
        "platform": sys.platform,
        "cwd": os.getcwd(),
    }
    for mod in ["fastapi", "uvicorn", "httpx", "pydantic", "starlette"]:
        try:
            m = importlib.import_module(mod)
            info[mod] = getattr(m, "__version__", "?")
        except Exception as e:
            info[mod] = f"err: {e}"
    return info