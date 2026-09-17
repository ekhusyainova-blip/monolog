# core_backend/stub_endpoints.py
# Эндпоинты заглушки: /ai/apply, /ai/apply_raw, /code/check.

import ast
import asyncio
import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from core_backend.stub_github import _get_sha, _get_content, _put_file


router = APIRouter()


class AIApplyRequest(BaseModel):
    path: str
    content: str
    message: str = "AI apply"


@router.post("/ai/apply")
async def ai_apply(body: AIApplyRequest):
    path = body.path.strip()
    content = body.content
    message = body.message.strip()

    if not path or not content:
        raise HTTPException(status_code=400, detail="Нужны path и content")

    FORBIDDEN = (".env", "requirements.txt", "Dockerfile")
    if any(path.endswith(f) for f in FORBIDDEN):
        raise HTTPException(status_code=403, detail=f"Файл {path} защищён")

    sha_before = await _get_sha(path)
    await _put_file(path, content, message)
    await asyncio.sleep(3)

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.get("https://ai-monolog.onrender.com/health")
            if r.status_code != 200:
                raise Exception(f"health вернул {r.status_code}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Health check не прошёл: {e}")

    return JSONResponse({"ok": True, "path": path, "sha_before": sha_before, "health": "ok"})


@router.post("/ai/apply_raw")
async def ai_apply_raw(request: Request, path: str, message: str = "AI apply raw"):
    """Принимает text/plain. path и message — в query."""
    raw = await request.body()
    try:
        content = raw.decode("utf-8")
    except Exception:
        raise HTTPException(status_code=400, detail="Тело должно быть UTF-8 текстом")

    if not path or not content:
        raise HTTPException(status_code=400, detail="Нужны path и body")

    FORBIDDEN = (".env", "requirements.txt", "Dockerfile")
    if any(path.endswith(f) for f in FORBIDDEN):
        raise HTTPException(status_code=403, detail=f"Файл {path} защищён")

    sha_before = await _get_sha(path)
    await _put_file(path, content, message)
    await asyncio.sleep(3)

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.get("https://ai-monolog.onrender.com/health")
            if r.status_code != 200:
                raise Exception(f"health вернул {r.status_code}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Health check не прошёл: {e}")

    return JSONResponse({"ok": True, "path": path, "sha_before": sha_before, "health": "ok"})


@router.get("/code/check")
async def code_check(path: str):
    content = await _get_content(path)
    if content is None:
        return JSONResponse({"exists": False, "path": path})
    try:
        ast.parse(content)
        return JSONResponse({"exists": True, "valid": True, "path": path})
    except SyntaxError as e:
        return JSONResponse({
            "exists": True,
            "valid": False,
            "path": path,
            "error": str(e),
            "line": e.lineno,
            "offset": e.offset,
            "text": (e.text or "").strip(),
        })
        
        # --- /code/diagnose (проверка всех .py файлов одним вызовом) ---
import httpx as _httpx  # локальный алиас, чтобы не путаться


@router.get("/code/diagnose")
async def code_diagnose():
    """
    Проверяет синтаксис всех .py файлов в core_backend/ и app.py.
    Возвращает список сломанных с указанием строки.
    """
    from core_backend.stub_github import GITHUB_TOKEN, GITHUB_REPO, GITHUB_BRANCH, GITHUB_API

    # 1. Получить дерево файлов репозитория
    url = f"{GITHUB_API}/repos/{GITHUB_REPO}/git/trees/{GITHUB_BRANCH}"
    headers = {"Accept": "application/vnd.github+json"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"

    async with _httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get(url, headers=headers, params={"recursive": "1"})
        if r.status_code >= 400:
            raise HTTPException(status_code=502, detail=f"GitHub tree: {r.status_code}")
        tree = r.json().get("tree", [])

    # 2. Фильтр: только .py в core_backend/ и app.py
    py_files = []
    for item in tree:
        p = item.get("path", "")
        if item.get("type") != "blob":
            continue
        if not p.endswith(".py"):
            continue
        if p.startswith("core_backend/") or p == "app.py":
            py_files.append(p)

    # 3. Проверить каждый
    results = []
    invalid = []
    for path in py_files:
        try:
            content = await _get_content(path)
        except Exception as e:
            invalid.append({
                "path": path,
                "error": f"не удалось прочитать: {e}",
                "line": None,
                "text": None,
            })
            continue

        if content is None:
            continue

        try:
            ast.parse(content)
            results.append({"path": path, "valid": True})
        except SyntaxError as e:
            item = {
                "path": path,
                "valid": False,
                "error": str(e),
                "line": e.lineno,
                "offset": e.offset,
                "text": (e.text or "").strip(),
            }
            results.append(item)
            invalid.append(item)

    return JSONResponse({
        "total": len(py_files),
        "valid_count": len(py_files) - len(invalid),
        "invalid_count": len(invalid),
        "invalid": invalid,
        "all": results,
    })