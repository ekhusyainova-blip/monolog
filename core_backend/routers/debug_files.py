# core_backend/routers/debug_files.py
# Диагностика файлов в контейнере.

import os
import time

from fastapi import APIRouter
from fastapi.responses import JSONResponse


router = APIRouter(prefix="/debug/files", tags=["debug-files"])


def _ls(path: str):
    try:
        return sorted(os.listdir(path)) if os.path.exists(path) else None
    except Exception as e:
        return f"err: {e}"


@router.get("/list")
async def files_list():
    return {
        "cwd": _ls("."),
        "core_backend": _ls("core_backend"),
        "routers": _ls("core_backend/routers"),
        "core": _ls("core"),
        "adaptive": _ls("adaptive"),
        "prompts": _ls("prompts"),
        "public": _ls("public"),
    }


@router.get("/info")
async def files_info(path: str):
    if not os.path.exists(path):
        return JSONResponse({"exists": False, "path": path})
    try:
        size = os.path.getsize(path)
        mtime = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(os.path.getmtime(path)))
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            first = f.read(500)
        return JSONResponse({
            "exists": True, "path": path, "size": size,
            "mtime": mtime, "first_500": first,
        })
    except Exception as e:
        return JSONResponse({"exists": True, "path": path, "error": str(e)})


@router.get("/index_html")
async def files_index_html():
    if not os.path.exists("index.html"):
        return JSONResponse({"exists": False})
    with open("index.html", "r", encoding="utf-8") as f:
        content = f.read()
    return JSONResponse({"exists": True, "size": len(content), "content": content})


@router.get("/mime_static_check")
async def mime_static_check():
    return {
        "core_backend/mime_static.py": os.path.exists("core_backend/mime_static.py"),
        "core/mime_static.py": os.path.exists("core/mime_static.py"),
        "mime_static.py": os.path.exists("mime_static.py"),
        "full_app_exists": os.path.exists("core_backend/full_app.py"),
        "full_app_first_500": (
            open("core_backend/full_app.py", encoding="utf-8").read(500)
            if os.path.exists("core_backend/full_app.py") else None
        ),
    }