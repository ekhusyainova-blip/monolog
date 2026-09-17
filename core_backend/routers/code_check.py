# core_backend/routers/code_check.py
# Эндпоинты /code/check и /code/diagnose — проверка синтаксиса файлов.
# APIRouter — подключается автоматически.

import ast
from fastapi import APIRouter
from fastapi.responses import JSONResponse

from core_backend.github_api import github_get_file


router = APIRouter(tags=["code"])


@router.get("/code/check")
async def code_check(path: str):
    """Проверяет синтаксис одного файла."""
    content, _ = await github_get_file(path)
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


@router.get("/code/diagnose")
async def code_diagnose():
    """Проверяет синтаксис всех .py файлов в core_backend/ и app.py."""
    import httpx
    from core_backend.config import GITHUB_TOKEN, GITHUB_REPO, GITHUB_BRANCH, GITHUB_API

    # 1. Получить дерево файлов
    url = f"{GITHUB_API}/repos/{GITHUB_REPO}/git/trees/{GITHUB_BRANCH}"
    headers = {"Accept": "application/vnd.github+json"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"

    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get(url, headers=headers, params={"recursive": "1"})
        if r.status_code >= 400:
            return JSONResponse({"error": f"GitHub tree: {r.status_code}"}, status_code=502)
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
    invalid = []
    for path in py_files:
        content, _ = await github_get_file(path)
        if content is None:
            continue
        try:
            ast.parse(content)
        except SyntaxError as e:
            invalid.append({
                "path": path,
                "valid": False,
                "error": str(e),
                "line": e.lineno,
                "offset": e.offset,
                "text": (e.text or "").strip(),
            })

    return JSONResponse({
        "total": len(py_files),
        "valid_count": len(py_files) - len(invalid),
        "invalid_count": len(invalid),
        "invalid": invalid,
    })