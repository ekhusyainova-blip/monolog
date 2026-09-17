# core_backend/stub.py
# Заглушка Monolog — используется, когда роутеры не готовы.
# Активируется через APP_MODE=stub в env.

import os
import ast
import base64
import asyncio

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="Monolog (stub)")

app.mount("/core", StaticFiles(directory="core"), name="core")
app.mount("/adaptive", StaticFiles(directory="adaptive"), name="adaptive")
app.mount("/blog", StaticFiles(directory="blog"), name="blog")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "").strip()
GITHUB_REPO = os.getenv("GITHUB_REPO", "ekhusyainova-blip/monolog").strip()
GITHUB_BRANCH = os.getenv("GITHUB_BRANCH", "main").strip()
GITHUB_API = "https://api.github.com"


async def _get_sha(path: str):
    url = f"{GITHUB_API}/repos/{GITHUB_REPO}/contents/{path}"
    headers = {"Accept": "application/vnd.github+json"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get(url, headers=headers, params={"ref": GITHUB_BRANCH})
        if r.status_code == 200:
            return r.json().get("sha")
        return None


async def _get_content(path: str):
    url = f"{GITHUB_API}/repos/{GITHUB_REPO}/contents/{path}"
    headers = {"Accept": "application/vnd.github+json"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get(url, headers=headers, params={"ref": GITHUB_BRANCH})
        if r.status_code == 404:
            return None
        if r.status_code >= 400:
            raise HTTPException(status_code=502, detail=f"GitHub: {r.status_code}")
        data = r.json()
        try:
            return base64.b64decode(data.get("content", "")).decode("utf-8")
        except Exception:
            return None


async def _put_file(path: str, content: str, message: str):
    if not GITHUB_TOKEN:
        raise HTTPException(status_code=503, detail="GITHUB_TOKEN не настроен")
    sha = await _get_sha(path)
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


# --- /ai/apply (JSON body) ---
class AIApplyRequest(BaseModel):
    path: str
    content: str
    message: str = "AI apply"


@app.post("/ai/apply")
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

    return JSONResponse({
        "ok": True,
        "path": path,
        "sha_before": sha_before,
        "health": "ok",
    })


# --- /ai/apply_raw (text/plain body) ---
@app.post("/ai/apply_raw")
async def ai_apply_raw(request: Request, path: str, message: str = "AI apply raw"):
    """
    Принимает сырой текст (не JSON). path и message — в query.
    Через reqbin.com: body=сырой текст, URL=/ai/apply_raw?path=...&message=...
    """
    raw = await request.body()
    try:
        content = raw.decode("utf-8")
    except Exception:
        raise HTTPException(status_code=400, detail="Тело должно быть UTF-8 тек_MODEстом")

",    if not path or not content:
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

    return JSONResponse({
        "ok": True,
        "path": path,
        "sha_before": sha_before,
        "health": "ok",
    })


# --- /code/check (проверка синтаксиса файла) ---
@app.get("/code/check")
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


# --- базовое ---
@app.get("/")
async def root():
    return FileResponse("index.html")


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "version": "stub+ai",
        "mode": "заглушка (отдельный файл core_backend/stub.py)",
        "app_mode": os.getenv("APP "stub"),
        "github_ready": bool(GITHUB_TOKEN),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("core_backend.stub:app", host="0.0.0.0", port=int(os.getenv("PORT", 8000)))