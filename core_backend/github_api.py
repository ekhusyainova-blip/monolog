# core_backend/github_api.py
# Работа с GitHub API: чтение и запись файлов в репозиторий.
# Используется в code_ai.py, public_layer.py и других модулях.
# Без роутера — только функции.

import json
import base64
from typing import Optional, Tuple, Any

import httpx
from fastapi import HTTPException

from core_backend.config import (
    GITHUB_TOKEN,
    GITHUB_REPO,
    GITHUB_BRANCH,
    GITHUB_API,
)


def _headers() -> dict:
    h = {"Accept": "application/vnd.github+json"}
    if GITHUB_TOKEN:
        h["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    return h


async def github_get_sha(path: str) -> Optional[str]:
    """Возвращает sha файла или None, если файла нет."""
    url = f"{GITHUB_API}/repos/{GITHUB_REPO}/contents/{path}"
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get(url, headers=_headers(), params={"ref": GITHUB_BRANCH})
        if r.status_code == 200:
            return r.json().get("sha")
        return None


async def github_get_json(path: str) -> Tuple[Optional[Any], Optional[str]]:
    """Читает JSON-файл из репозитория. Возвращает (parsed, sha)."""
    url = f"{GITHUB_API}/repos/{GITHUB_REPO}/contents/{path}"
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get(url, headers=_headers(), params={"ref": GITHUB_BRANCH})
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


async def github_put_json(path: str, content_obj: Any, message: str) -> bool:
    """Сохраняет JSON-объект в репозиторий. Создаёт или обновляет файл."""
    if not GITHUB_TOKEN:
        raise HTTPException(status_code=503, detail="GITHUB_TOKEN не настроен")
    _, sha = await github_get_json(path)
    content = json.dumps(content_obj, ensure_ascii=False, indent=2)
    content_b64 = base64.b64encode(content.encode("utf-8")).decode("utf-8")
    url = f"{GITHUB_API}/repos/{GITHUB_REPO}/contents/{path}"
    body = {"message": message, "content": content_b64, "branch": GITHUB_BRANCH}
    if sha:
        body["sha"] = sha
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.put(url, headers=_headers(), json=body)
        if r.status_code >= 400:
            raise HTTPException(status_code=502, detail=f"Не удалось сохранить {path}")
        return True


async def github_get_file(path: str) -> Tuple[Optional[str], Optional[str]]:
    """Читает файл как текст. Возвращает (content, sha)."""
    url = f"{GITHUB_API}/repos/{GITHUB_REPO}/contents/{path}"
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get(url, headers=_headers(), params={"ref": GITHUB_BRANCH})
        if r.status_code == 404:
            return None, None
        if r.status_code >= 400:
            raise HTTPException(status_code=502, detail=f"Не удалось прочитать {path}")
        data = r.json()
        try:
            content = base64.b64decode(data.get("content", "")).decode("utf-8")
        except Exception:
            content = ""
        return content, data.get("sha")


async def github_put_file(path: str, content: str, message: str) -> dict:
    """Сохраняет текстовый файл в репозиторий. Создаёт или обновляет."""
    if not GITHUB_TOKEN:
        raise HTTPException(status_code=503, detail="GITHUB_TOKEN не настроен")
    sha = await github_get_sha(path)
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