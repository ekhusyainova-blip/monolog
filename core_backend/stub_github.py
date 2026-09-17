# core_backend/stub_github.py
# Работа с GitHub API для заглушки.

import os
import base64
import httpx
from fastapi import HTTPException

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "").strip()
GITHUB_REPO = os.getenv("GITHUB_REPO", "ekhusyainova-blip/monolog").strip()
GITHUB_BRANCH = os.getenv("GITHUB_BRANCH", "main").strip()
GITHUB_API = "https://api.github.com"


def _headers():
    h = {"Accept": "application/vnd.github+json"}
    if GITHUB_TOKEN:
        h["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    return h


async def _get_sha(path: str):
    url = f"{GITHUB_API}/repos/{GITHUB_REPO}/contents/{path}"
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get(url, headers=_headers(), params={"ref": GITHUB_BRANCH})
        if r.status_code == 200:
            return r.json().get("sha")
        return None


async def _get_content(path: str):
    url = f"{GITHUB_API}/repos/{GITHUB_REPO}/contents/{path}"
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get(url, headers=_headers(), params={"ref": GITHUB_BRANCH})
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
    body = {"message": message, "content": content_b64, "branch": GITHUB_BRANCH}
    if sha:
        body["sha"] = sha
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.put(url, headers=_headers(), json=body)
        if r.status_code >= 400:
            raise HTTPException(status_code=502, detail=f"GitHub: {r.status_code} {r.text[:200]}")
        return r.json()