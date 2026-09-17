# core_backend/routers/debug_system.py
# Роуты, логи, сводный отчёт.

import os
import time

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse


router = APIRouter(prefix="/debug/system", tags=["debug-system"])

_START_TIME = time.time()


@router.get("/routes")
async def routes_list(request: Request):
    routes = []
    for r in request.app.routes:
        methods = getattr(r, "methods", None)
        if methods:
            routes.append({"path": r.path, "methods": sorted(methods)})
        else:
            routes.append({"path": r.path, "methods": "mount"})
    return JSONResponse({"count": len(routes), "routes": routes})


@router.get("/uptime")
async def uptime():
    return {
        "uptime_seconds": round(time.time() - _START_TIME, 1),
        "commit": os.environ.get("RENDER_GIT_COMMIT"),
        "branch": os.environ.get("RENDER_GIT_BRANCH"),
        "app_mode": os.environ.get("APP_MODE"),
    }


@router.get("/full_report")
async def full_report(request: Request):
    """Сводный отчёт по ключевым точкам."""
    import mimetypes
    import importlib

    report = {"at": time.strftime("%Y-%m-%d %H:%M:%S")}

    # MIME
    report["mime"] = {
        "js": mimetypes.guess_type("test.js"),
        "css": mimetypes.guess_type("test.css"),
        "json": mimetypes.guess_type("test.json"),
    }

    # MimeStaticFiles
    try:
        mod = importlib.import_module("core_backend.mime_static")
        report["mime_static"] = {
            "import_ok": True,
            "has_class": hasattr(mod, "MimeStaticFiles"),
            "test_js": mod.guess_mime("test.js") if hasattr(mod, "guess_mime") else None,
        }
    except Exception as e:
        report["mime_static"] = {"import_ok": False, "error": str(e)}

    # full_app
    try:
        full = importlib.import_module("core_backend.full_app")
        src = open(full.__file__, "r", encoding="utf-8").read() if full.__file__ else ""
        report["full_app"] = {
            "uses_MimeStaticFiles": "MimeStaticFiles" in src,
            "uses_only_StaticFiles": ("StaticFiles" in src and "MimeStaticFiles" not in src),
        }
    except Exception as e:
        report["full_app"] = {"error": str(e)}

    # Files
    def ls(p):
        try:
            return sorted(os.listdir(p)) if os.path.exists(p) else None
        except Exception:
            return None

    report["files"] = {
        "routers": ls("core_backend/routers"),
        "core_backend": ls("core_backend"),
        "core": ls("core"),
        "adaptive": ls("adaptive"),
    }

    return JSONResponse(report)