# adaptive/github_store.py — работа с файлами в GitHub.
# Используется public, code и patches. Одно место — одна логика.

import os
import json
import base64
import logging

import httpx
from fastapi import HTTPException

log = logging.getLogger("monolog")

GITHUB_API = "https://api.github.com"
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "").strip()
GITHUB_REPO = os.getenv("GITHUB_REPO", "ekhusyainova-blip/monolog").strip()
GITHUB_BRANCH = os.getenv("GITHUB_BRANCH", "main").strip()
CODE_BRANCH = os.getenv("CODE_BRANCH", "dev").strip()


async def get_json(path: str, branch: str = None):
    url = f"{GITHUB_API}/repos/{GITHUB_REPO}/contents/{path}"
    headers = {"Accept": "application/vnd.github+json"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    ref = branch or GITHUB_BRANCH
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get(url, headers=headers, params={"ref": ref})
        if r.status_code == 404:
            return None, None
        if r.status_code >= 400:
            raise HTTPException(status_code=502, detail=f"Не удалось прочитать {path}")
        data = r.json()
        try:
            raw = base64.b64decode(data.get("content", "")).decode("utf-8")
            parsed = json.loads(raw) if raw.strip() else None
        except Exception:
            parsed = None
        return parsed, data.get("sha")


async def put_json(path: str, content_obj, message: str, branch: str = None):
    if not GITHUB_TOKEN:
        raise HTTPException(status_code=503, detail="GITHUB_TOKEN не настроен")
    ref = branch or GITHUB_BRANCH
    _, sha = await get_json(path, ref)
    content = json.dumps(content_obj, ensure_ascii=False, indent=2)
    content_b64 = base64.b64encode(content.encode("utf-8")).decode("utf-8")
    url = f"{GITHUB_API}/repos/{GITHUB_REPO}/contents/{path}"
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {GITHUB_TOKEN}",
    }
    body = {"message": message, "content": content_b64, "branch": ref}
    if sha:
        body["sha"] = sha
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.put(url, headers=headers, json=body)
        if r.status_code >= 400:
            raise HTTPException(status_code=502, detail=f"Не удалось сохранить {path}")
        data = r.json()
        return {
            "ok": True,
            "path": path,
            "branch": ref,
            "commit_sha": data.get("commit", {}).get("sha"),
            "html_url": data.get("commit", {}).get("html_url"),
        }


async def read_text(path: str, branch: str = None):
    url = f"{GITHUB_API}/repos/{GITHUB_REPO}/contents/{path}"
    headers = {"Accept": "application/vnd.github+json"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    ref = branch or GITHUB_BRANCH
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get(url, headers=headers, params={"ref": ref})
        if r.status_code == 404:
            return None, None, ref
        if r.status_code >= 400:
            raise HTTPException(status_code=502, detail=f"Не удалось прочитать {path}")
        data = r.json()
        try:
            content = base64.b64decode(data.get("content", "")).decode("utf-8")
        except Exception:
            content = ""
        return content, data.get("sha"), ref


async def save_text(path: str, content: str, message: str, branch: str = None):
    if not GITHUB_TOKEN:
        raise HTTPException(status_code=503, detail="GITHUB_TOKEN не настроен")
    ref = branch or GITHUB_BRANCH
    url = f"{GITHUB_API}/repos/{GITHUB_REPO}/contents/{path}"
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {GITHUB_TOKEN}",
    }
    sha = None
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get(url, headers=headers, params={"ref": ref})
        if r.status_code == 200:
            sha = r.json().get("sha")
        content_b64 = base64.b64encode(content.encode("utf-8")).decode("utf-8")
        payload = {"message": message, "content": content_b64, "branch": ref}
        if sha:
            payload["sha"] = sha
        r = await client.put(url, headers=headers, json=payload)
        if r.status_code >= 400:
            raise HTTPException(status_code=502, detail=f"Не удалось сохранить {path}")
        data = r.json()
        return {
            "ok": True,
            "path": path,
            "branch": ref,
            "commit_sha": data.get("commit", {}).get("sha"),
            "html_url": data.get("commit", {}).get("html_url"),
        }