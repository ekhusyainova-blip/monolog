# core_backend/routers/debug_github.py
# Диагностика GitHub-репозитория.

import base64

import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from core_backend.config import (
    GITHUB_TOKEN, GITHUB_REPO, GITHUB_BRANCH, GITHUB_API,
)


router = APIRouter(prefix="/debug/github", tags=["debug-github"])


def _gh_headers():
    h = {"Accept": "application/vnd.github+json"}
    if GITHUB_TOKEN:
        h["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    return h


@router.get("/file_info")
async def file_info(path: str):
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
            "exists": True, "path": path,
            "size": data.get("size"), "sha": data.get("sha"),
            "first_500": raw[:500],
        })


@router.get("/branches")
async def branches():
    url = f"{GITHUB_API}/repos/{GITHUB_REPO}/branches"
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get(url, headers=_gh_headers())
        if r.status_code >= 400:
            raise HTTPException(status_code=502, detail=f"GitHub: {r.status_code}")
        return JSONResponse({"branches": [b.get("name") for b in r.json()]})


@router.get("/commits")
async def commits(limit: int = 10):
    url = f"{GITHUB_API}/repos/{GITHUB_REPO}/commits"
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get(url, headers=_gh_headers(),
                             params={"sha": GITHUB_BRANCH, "per_page": limit})
        if r.status_code >= 400:
            raise HTTPException(status_code=502, detail=f"GitHub: {r.status_code}")
        return JSONResponse({
            "commits": [
                {
                    "sha": c.get("sha", "")[:8],
                    "msg": (c.get("commit", {}).get("message") or "")[:80],
                    "date": c.get("commit", {}).get("author", {}).get("date"),
                }
                for c in r.json()
            ]
        })