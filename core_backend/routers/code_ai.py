# core_backend/code_ai.py
# Роутер /code/* (чтение, сохранение) и /ai/apply (автоматизация разработки).
# APIRouter — подключается в app.py.

import hmac
import asyncio
import base64
from typing import Optional

import httpx
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from core_backend.config import (
    AUTHOR_SECRET,
    GITHUB_TOKEN,
    GITHUB_REPO,
    GITHUB_BRANCH,
    CODE_BRANCH,
    GITHUB_API,
)
from core_backend.github_api import (
    github_get_sha,
    github_get_file,
    github_put_file,
)


router = APIRouter(tags=["code"])


def _safe_eq(a: str, b: str) -> bool:
    if not a or not b:
        return False
    return hmac.compare_digest(a, b)


def _check_author(request: Request):
    if not AUTHOR_SECRET:
        raise HTTPException(status_code=503, detail="Ключ автора не настроен")
    key = request.headers.get("X-Author-Key", "").strip()
    if not _safe_eq(key, AUTHOR_SECRET):
        raise HTTPException(status_code=403, detail="Неверный ключ автора.")


# --- /code/read ---
@router.get("/code/read")
async def code_read(request: Request, path: str):
    _check_author(request)
    if not GITHUB_TOKEN:
        raise HTTPException(status_code=503, detail="GITHUB_TOKEN не настроен")
    url = f"{GITHUB_API}/repos/{GITHUB_REPO}/contents/{path}"
    headers = {"Accept": "application/vnd.github+json",
               "Authorization": f"Bearer {GITHUB_TOKEN}"}
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get(url, headers=headers, params={"ref": CODE_BRANCH})
        branch_used = CODE_BRANCH
        if r.status_code == 404:
            r = await client.get(url, headers=headers, params={"ref": GITHUB_BRANCH})
            branch_used = GITHUB_BRANCH
        if r.status_code == 404:
            return JSONResponse({"exists": False, "path": path, "content": None, "sha": None, "branch": branch_used})
        if r.status_code >= 400:
            raise HTTPException(status_code=502, detail="Не удалось прочитать файл")
        data = r.json()
        try:
            content = base64.b64decode(data.get("content", "")).decode("utf-8")
        except Exception:
            content = ""
        return JSONResponse({
            "exists": True, "path": path,
            "content": content, "sha": data.get("sha"), "branch": branch_used,
        })


# --- /code/save ---
@router.post("/code/save")
async def code_save(request: Request):
    _check_author(request)
    if not GITHUB_TOKEN:
        raise HTTPException(status_code=503, detail="GITHUB_TOKEN не настроен")
    body = await request.json()
    path = (body.get("path") or "").strip()
    content = body.get("content") or ""
    message = (body.get("message") or f"Update {path}").strip()
    if not path:
        raise HTTPException(status_code=400, detail="Не указан путь")

    url = f"{GITHUB_API}/repos/{GITHUB_REPO}/contents/{path}"
    headers = {"Accept": "application/vnd.github+json",
               "Authorization": f"Bearer {GITHUB_TOKEN}"}
    sha = None
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get(url, headers=headers, params={"ref": CODE_BRANCH})
        if r.status_code == 200:
            sha = r.json().get("sha")
        content_b64 = base64.b64encode(content.encode("utf-8")).decode("utf-8")
        payload = {"message": message, "content": content_b64, "branch": CODE_BRANCH}
        if sha:
            payload["sha"] = sha
        r = await client.put(url, headers=headers, json=payload)
        if r.status_code >= 400:
            raise HTTPException(status_code=502, detail="Не удалось сохранить код")
        data = r.json()
        return JSONResponse({
            "ok": True, "path": path, "branch": CODE_BRANCH,
            "commit_sha": data.get("commit", {}).get("sha"),
            "html_url": data.get("commit", {}).get("html_url"),
        })


# --- /ai/apply ---
class AIApplyRequest(BaseModel):
    path: str
    content: str
    message: str = "AI apply"


@router.post("/ai/apply")
async def ai_apply(body: AIApplyRequest):
    """
    Сохраняет файл в main. Проверяет /health. При неудаче — не сохраняет.
    """
    path = body.path.strip()
    content = body.content
    message = body.message.strip()

    if not path:
        raise HTTPException(status_code=400, detail="Нужно поле path")
    if not content:
        raise HTTPException(status_code=400, detail="Нужно поле content")

    FORBIDDEN = (".env", "requirements.txt", "Dockerfile")
    if any(path.endswith(f) for f in FORBIDDEN):
        raise HTTPException(status_code=403, detail=f"Файл {path} защищён от автоправок")

    sha_before = await github_get_sha(path)
    await github_put_file(path, content, message)

    await asyncio.sleep(3)

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.get("https://ai-monolog.onrender.com/health")
            if r.status_code != 200:
                raise Exception(f"health вернул {r.status_code}")
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Health check не прошёл. Причина: {e}",
        )

    return JSONResponse({
        "ok": True,
        "path": path,
        "sha_before": sha_before,
        "message": message,
        "health": "ok",
    })
