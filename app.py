# app.py (заглушка + /ai/apply)
# Временный backend: Render запускается, /health работает,
# и есть /ai/apply — чтобы заливать файлы через API, а не через GitHub-веб.

import os
import base64
import asyncio

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="Monolog (stub + ai/apply)")

app.mount("/core", StaticFiles(directory="core"), name="core")
app.mount("/adaptive", StaticFiles(directory="adaptive"), name="adaptive")
app.mount("/public", StaticFiles(directory="public"), name="public")
app.mount("/blog", StaticFiles(directory="blog"), name="blog")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# --- GitHub ---
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "").strip()
GITHUB_REPO = os.getenv("GITHUB_REPO", "ekhusyainova-blip/monolog").strip()
GITHUB_BRANCH = os.getenv("GITHUB_BRANCH", "main").strip()
GITHUB_API = "https://api.github.com"


async def github_get_sha(path: str):
    """Возвращает sha файла или None, если файла нет."""
    url = f"{GITHUB_API}/repos/{GITHUB_REPO}/contents/{path}"
    headers = {"Accept": "application/vnd.github+json"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get(url, headers=headers, params={"ref": GITHUB_BRANCH})
        if r.status_code == 200:
            return r.json().get("sha")
        return None


async def github_put_file(path: str, content: str, message: str):
    """Сохраняет файл в репозиторий."""
    if not GITHUB_TOKEN:
        raise HTTPException(status_code=503, detail="GITHUB_TOKEN не настроен")
    sha = await github_get_sha(path)
    content_b64 = base64.b64encode(content.encode("utf-8")).decode("utf-8")
    url = f"{GITHUB_API}/repos/{GITHUB_REPO}/contents/{path}"
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {GITHUB_TOKEN}",
    }
    body = {"message": message, "content": content_b64, "branch": GITHUB_BRANCH}
    if sha:
        body["sha"] = sha
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.put(url, headers=headers, json=body)
        if r.status_code >= 400:
            raise HTTPException(status_code=502, detail=f"GitHub: {r.status_code} {r.text[:200]}")
        return r.json()


# --- /ai/apply ---
class AIApplyRequest(BaseModel):
    path: str
    content: str
    message: str = "AI apply"


@app.post("/ai/apply")
async def ai_apply(body: AIApplyRequest):
    """
    Сохраняет файл в репозиторий (main).
    Проверяет /health после сохранения. При неудаче — откат.
    """
    path = body.path.strip()
    content = body.content
    message = body.message.strip()

    if not path or not content:
        raise HTTPException(status_code=400, detail="Нужны path и content")

    # Защита
    FORBIDDEN = (".env", "requirements.txt", "Dockerfile")
    if any(path.endswith(f) for f in FORBIDDEN):
        raise HTTPException(status_code=403, detail=f"Файл {path} защищён")

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


# --- базовое ---
@app.get("/")
async def root():
    return FileResponse("index.html")


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "version": "stub+ai",
        "mode": "заглушка с /ai/apply",
        "github_ready": bool(GITHUB_TOKEN),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=int(os.getenv("PORT", 8000)))