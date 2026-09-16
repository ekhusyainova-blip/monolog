# adaptive/code.py — служебные эндпоинты: code, blog, releases, management.
# Требуют AUTHOR_SECRET или MANAGEMENT_KEY.

import os
import json
import time
import logging

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse

from adaptive.github_store import (
    get_json, put_json, read_text, save_text,
    GITHUB_TOKEN, CODE_BRANCH, GITHUB_BRANCH,
)

log = logging.getLogger("monolog")

AUTHOR_SECRET = os.getenv("AUTHOR_SECRET", "").strip()
MANAGEMENT_KEY = os.getenv("MANAGEMENT_KEY", "").strip()

BLOG_PATH = "blog/posts.json"
RELEASES_PATH = "releases.json"


def _safe_eq(a: str, b: str) -> bool:
    import hmac
    if not a or not b:
        return False
    return hmac.compare_digest(a, b)


def check_author(request: Request):
    if not AUTHOR_SECRET:
        raise HTTPException(status_code=503, detail="Ключ автора не настроен")
    key = request.headers.get("X-Author-Key", "").strip()
    if not _safe_eq(key, AUTHOR_SECRET):
        raise HTTPException(status_code=403, detail="Неверный ключ автора. Проверьте в настройках.")


def check_management(request: Request):
    if not MANAGEMENT_KEY:
        raise HTTPException(status_code=503, detail="Ключ Управления не настроен")
    key = request.headers.get("X-Management-Key", "").strip()
    if not _safe_eq(key, MANAGEMENT_KEY):
        raise HTTPException(status_code=403, detail="Неверный ключ Управления. Проверьте в настройках.")


router = APIRouter()


# --- Blog ---
@router.get("/blog")
async def blog_list():
    data, _ = await get_json(BLOG_PATH)
    posts = data if isinstance(data, list) else []
    metas = []
    for p in posts:
        metas.append({
            "id": p.get("id"),
            "title": p.get("title"),
            "tags": p.get("tags", []),
            "author": p.get("author", "Автор"),
            "created_at": p.get("created_at"),
            "updated_at": p.get("updated_at"),
            "preview": (p.get("body") or "")[:180],
        })
    metas.sort(key=lambda x: x.get("created_at") or "", reverse=True)
    return JSONResponse({"posts": metas, "count": len(metas)})


@router.get("/blog/{post_id}")
async def blog_get(post_id: str):
    data, _ = await get_json(BLOG_PATH)
    posts = data if isinstance(data, list) else []
    for p in posts:
        if p.get("id") == post_id:
            return JSONResponse(p)
    raise HTTPException(status_code=404, detail="Статья не найдена")


@router.post("/blog/publish")
async def blog_publish(request: Request):
    check_author(request)
    body = await request.json()
    title = (body.get("title") or "").strip()
    text = (body.get("body") or "").strip()
    tags = body.get("tags") or []
    author = (body.get("author") or "Автор").strip()
    if not title or not text:
        raise HTTPException(status_code=400, detail="Нужны заголовок и текст")

    data, _ = await get_json(BLOG_PATH)
    posts = data if isinstance(data, list) else []
    post_id = "post_" + str(int(time.time() * 1000))
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    new_post = {
        "id": post_id, "title": title, "body": text,
        "tags": tags if isinstance(tags, list) else [],
        "author": author, "created_at": now, "updated_at": now,
    }
    posts.append(new_post)
    await put_json(BLOG_PATH, posts, f"Blog: publish '{title[:50]}'")
    return JSONResponse({"ok": True, "id": post_id})


@router.delete("/blog/{post_id}")
async def blog_delete(post_id: str, request: Request):
    check_author(request)
    data, _ = await get_json(BLOG_PATH)
    posts = data if isinstance(data, list) else []
    new_posts = [p for p in posts if p.get("id") != post_id]
    if len(new_posts) == len(posts):
        raise HTTPException(status_code=404, detail="Статья не найдена")
    await put_json(BLOG_PATH, new_posts, f"Blog: delete '{post_id}'")
    return JSONResponse({"ok": True})


# --- Code ---
@router.get("/code/read")
async def code_read(request: Request, path: str):
    check_author(request)
    if not GITHUB_TOKEN:
        raise HTTPException(status_code=503, detail="GITHUB_TOKEN не настроен")
    content, sha, branch_used = await read_text(path, branch=CODE_BRANCH)
    if content is None:
        content2, sha2, branch_used2 = await read_text(path, branch=GITHUB_BRANCH)
        if content2 is None:
            return JSONResponse({"exists": False, "path": path, "content": None, "sha": None, "branch": branch_used})
        return JSONResponse({"exists": True, "path": path, "content": content2, "sha": sha2, "branch": branch_used2})
    return JSONResponse({"exists": True, "path": path, "content": content, "sha": sha, "branch": branch_used})


@router.post("/code/save")
async def code_save(request: Request):
    check_author(request)
    if not GITHUB_TOKEN:
        raise HTTPException(status_code=503, detail="GITHUB_TOKEN не настроен")
    body = await request.json()
    path = (body.get("path") or "").strip()
    content = body.get("content") or ""
    message = (body.get("message") or f"Update {path}").strip()
    if not path:
        raise HTTPException(status_code=400, detail="Не указан путь")
    result = await save_text(path, content, message, branch=CODE_BRANCH)
    return JSONResponse(result)


# --- Releases ---
@router.get("/releases")
async def releases_list():
    data, _ = await get_json(RELEASES_PATH)
    if not isinstance(data, list):
        data = []
    return JSONResponse({"releases": data})


@router.post("/releases/save")
async def releases_save(request: Request):
    check_author(request)
    if not GITHUB_TOKEN:
        raise HTTPException(status_code=503, detail="GITHUB_TOKEN не настроен")
    body = await request.json()
    releases = body.get("releases") or []
    if not isinstance(releases, list):
        raise HTTPException(status_code=400, detail="releases должен быть списком")
    await put_json(RELEASES_PATH, releases, "Update releases")
    return JSONResponse({"ok": True, "count": len(releases)})


# --- Management ---
@router.post("/management/check")
async def management_check(request: Request):
    check_management(request)
    return JSONResponse({"ok": True, "management_mode": True})