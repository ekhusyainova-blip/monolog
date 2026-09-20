# meta_monolog.py — мета AI Monolog
# Слой D. Решает, что выводить. Слушает события B и C, кладёт в EVENTS.

import time
import base64
import httpx
from fastapi import HTTPException

from interpret_monolog import (
    on, emit, SEND, EVENTS,
    github_get_json, github_put_json,
)
from data_monolog import (
    PATHS, GITHUB_TOKEN, GITHUB_BRANCH, CODE_BRANCH, GITHUB_API, GITHUB_REPO,
    safe_log,
)

# ================= ЧАТ =================

@on("chat_error")
def on_chat_error(payload):
    SEND("error", payload)

@on("chat_done")
def on_chat_done(payload):
    SEND("chat_response", payload)

# ================= ХЕЛПЕРЫ GITHUB =================

async def _gh_get_sync(path):
    return await github_get_json(path)

async def _gh_put_sync(path, obj, msg):
    return await github_put_json(path, obj, msg)

# ================= ПУБЛИЧНЫЙ СЛОЙ =================

async def pub_templates_list(sort: str, limit: int):
    data, _ = await _gh_get_sync(PATHS["templates"])
    items = data if isinstance(data, list) else []
    keymap = {
        "top": lambda x: x.get("help_score") or 0,
        "help": lambda x: x.get("taken_count") or 0,
        "new": lambda x: x.get("at") or "",
    }
    items.sort(key=keymap.get(sort, keymap["new"]), reverse=True)
    return {"templates": items[:limit], "count": len(items)}

async def pub_templates_publish(body):
    template = body.get("template") or {}
    if not isinstance(template, dict) or not template.get("name"):
        raise HTTPException(status_code=400, detail="Нужно поле name")
    uid = (body.get("uid") or "").strip()
    if not uid:
        raise HTTPException(status_code=400, detail="Нужно поле uid")
    data, _ = await _gh_get_sync(PATHS["templates"])
    items = data if isinstance(data, list) else []
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    new_item = {
        "id": "tpl_" + str(int(time.time() * 1000)),
        "at": now, "uid": uid,
        "name": template.get("name"),
        "kind": template.get("kind") or "pattern",
        "content": template.get("content") or "",
        "tags": template.get("tags") or [],
        "taken_count": 0, "help_score": 0, "help_count": 0, "nohelp_count": 0,
    }
    items.append(new_item)
    await _gh_put_sync(PATHS["templates"], items, f"Public: template '{new_item['name'][:40]}'")
    rep, _ = await _gh_get_sync(PATHS["reputation"])
    rep = rep if isinstance(rep, dict) else {}
    user_rep = rep.get(uid) or {"given": 0, "taken": 0, "help_score": 0}
    user_rep["given"] = (user_rep.get("given") or 0) + 1
    rep[uid] = user_rep
    await _gh_put_sync(PATHS["reputation"], rep, f"Reputation: {uid} +given")
    return {"ok": True, "template": new_item}

async def pub_lots_list(sort: str, limit: int):
    data, _ = await _gh_get_sync(PATHS["lots"])
    items = data if isinstance(data, list) else []
    keymap = {"top": lambda x: x.get("help_score") or 0, "new": lambda x: x.get("at") or ""}
    items.sort(key=keymap.get(sort, keymap["new"]), reverse=True)
    return {"lots": items[:limit], "count": len(items)}

async def pub_lots_publish(body):
    lot = body.get("lot") or {}
    if not isinstance(lot, dict) or not lot.get("name"):
        raise HTTPException(status_code=400, detail="Нужно поле name")
    uid = (body.get("uid") or "").strip()
    if not uid:
        raise HTTPException(status_code=400, detail="Нужно поле uid")
    data, _ = await _gh_get_sync(PATHS["lots"])
    items = data if isinstance(data, list) else []
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    new_item = {
        "id": "lot_" + str(int(time.time() * 1000)),
        "at": now, "uid": uid,
        "name": lot.get("name"),
        "goal": lot.get("goal") or "",
        "price": lot.get("price") or "",
        "taken_count": 0, "help_score": 0, "help_count": 0, "nohelp_count": 0,
    }
    items.append(new_item)
    await _gh_put_sync(PATHS["lots"], items, f"Public: lot '{new_item['name'][:40]}'")
    rep, _ = await _gh_get_sync(PATHS["reputation"])
    rep = rep if isinstance(rep, dict) else {}
    user_rep = rep.get(uid) or {"given": 0, "taken": 0, "help_score": 0}
    user_rep["given"] = (user_rep.get("given") or 0) + 1
    rep[uid] = user_rep
    await _gh_put_sync(PATHS["reputation"], rep, f"Reputation: {uid} +given")
    return {"ok": True, "lot": new_item}

async def pub_take(body):
    target_id = (body.get("target_id") or "").strip()
    target_type = (body.get("target_type") or "").strip()
    uid = (body.get("uid") or "").strip()
    if not target_id or not target_type or not uid:
        raise HTTPException(status_code=400, detail="Нужны target_id, target_type, uid")
    path = PATHS["templates"] if target_type == "template" else PATHS["lots"]
    data, _ = await _gh_get_sync(path)
    items = data if isinstance(data, list) else []
    found = next((it for it in items if it.get("id") == target_id), None)
    if not found:
        raise HTTPException(status_code=404, detail="Не найдено")
    if found.get("uid") == uid:
        return {"ok": True, "self": True}
    found["taken_count"] = (found.get("taken_count") or 0) + 1
    await _gh_put_sync(path, items, f"Public: take '{target_id}'")
    rep, _ = await _gh_get_sync(PATHS["reputation"])
    rep = rep if isinstance(rep, dict) else {}
    user_rep = rep.get(uid) or {"given": 0, "taken": 0, "help_score": 0}
    user_rep["taken"] = (user_rep.get("taken") or 0) + 1
    rep[uid] = user_rep
    await _gh_put_sync(PATHS["reputation"], rep, f"Reputation: {uid} +taken")
    index_delta = -1.0 if target_type == "template" else -2.0
    return {"ok": True, "content": found.get("content") or found.get("goal") or "",
            "index_delta": index_delta, "author_uid": found.get("uid")}

async def pub_review(body):
    target_id = (body.get("target_id") or "").strip()
    target_type = (body.get("target_type") or "").strip()
    verdict = (body.get("verdict") or "").strip()
    uid = (body.get("uid") or "").strip()
    if not target_id or not target_type or verdict not in ("help", "nohelp") or not uid:
        raise HTTPException(status_code=400, detail="Нужны target_id, target_type, verdict (help|nohelp), uid")
    path = PATHS["templates"] if target_type == "template" else PATHS["lots"]
    data, _ = await _gh_get_sync(path)
    items = data if isinstance(data, list) else []
    found = next((it for it in items if it.get("id") == target_id), None)
    if not found:
        raise HTTPException(status_code=404, detail="Не найдено")
    key = "help_count" if verdict == "help" else "nohelp_count"
    found[key] = (found.get(key) or 0) + 1
    total = (found.get("help_count") or 0) + (found.get("nohelp_count") or 0)
    found["help_score"] = round((found.get("help_count") or 0) / total, 2) if total else 0
    await _gh_put_sync(path, items, f"Review: '{target_id}' ({verdict})")
    return {"ok": True, "help_score": found["help_score"]}

async def pub_profile(uid: str):
    rep, _ = await _gh_get_sync(PATHS["reputation"])
    rep = rep if isinstance(rep, dict) else {}
    user_rep = rep.get(uid) or {"given": 0, "taken": 0, "help_score": 0}
    reputation = (user_rep.get("given", 0) * 1.0) + (user_rep.get("help_score", 0) * 2.0) - (user_rep.get("taken", 0) * 0.3)
    return {"uid": uid, "given": user_rep.get("given", 0), "taken": user_rep.get("taken", 0),
            "help_score": user_rep.get("help_score", 0), "reputation": round(reputation, 2)}

# ================= БЛОГ =================

async def blog_list():
    data, _ = await _gh_get_sync(PATHS["blog"])
    posts = data if isinstance(data, list) else []
    metas = [{"id": p.get("id"), "title": p.get("title"), "tags": p.get("tags", []),
              "author": p.get("author", "Автор"), "created_at": p.get("created_at"),
              "updated_at": p.get("updated_at"), "preview": (p.get("body") or "")[:180]} for p in posts]
    metas.sort(key=lambda x: x.get("created_at") or "", reverse=True)
    return {"posts": metas, "count": len(metas)}

async def blog_get(post_id: str):
    data, _ = await _gh_get_sync(PATHS["blog"])
    posts = data if isinstance(data, list) else []
    for p in posts:
        if p.get("id") == post_id:
            return p
    raise HTTPException(status_code=404, detail="Статья не найдена")

async def blog_publish(body):
    title = (body.get("title") or "").strip()
    text = (body.get("body") or "").strip()
    tags = body.get("tags") or []
    author = (body.get("author") or "Автор").strip()
    if not title or not text:
        raise HTTPException(status_code=400, detail="Нужны заголовок и текст")
    data, _ = await _gh_get_sync(PATHS["blog"])
    posts = data if isinstance(data, list) else []
    post_id = "post_" + str(int(time.time() * 1000))
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    posts.append({"id": post_id, "title": title, "body": text,
                  "tags": tags if isinstance(tags, list) else [],
                  "author": author, "created_at": now, "updated_at": now})
    await _gh_put_sync(PATHS["blog"], posts, f"Blog: publish '{title[:50]}'")
    return {"ok": True, "id": post_id}

async def blog_delete(post_id: str):
    data, _ = await _gh_get_sync(PATHS["blog"])
    posts = data if isinstance(data, list) else []
    new_posts = [p for p in posts if p.get("id") != post_id]
    if len(new_posts) == len(posts):
        raise HTTPException(status_code=404, detail="Статья не найдена")
    await _gh_put_sync(PATHS["blog"], new_posts, f"Blog: delete '{post_id}'")
    return {"ok": True}

# ================= КОД =================

async def code_read(path: str):
    if not GITHUB_TOKEN:
        raise HTTPException(status_code=503, detail="GITHUB_TOKEN не настроен")
    url = f"{GITHUB_API}/repos/{GITHUB_REPO}/contents/{path}"
    headers = {"Accept": "application/vnd.github+json", "Authorization": f"Bearer {GITHUB_TOKEN}"}
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get(url, headers=headers, params={"ref": CODE_BRANCH})
        branch_used = CODE_BRANCH
        if r.status_code == 404:
            r = await client.get(url, headers=headers, params={"ref": GITHUB_BRANCH})
            branch_used = GITHUB_BRANCH
        if r.status_code == 404:
            return {"exists": False, "path": path, "content": None, "sha": None, "branch": branch_used}
        if r.status_code >= 400:
            raise HTTPException(status_code=502, detail="Не удалось прочитать файл")
        data = r.json()
        try:
            content = base64.b64decode(data.get("content", "")).decode("utf-8")
        except Exception:
            content = ""
        return {"exists": True, "path": path, "content": content, "sha": data.get("sha"), "branch": branch_used}

async def code_save(body):
    if not GITHUB_TOKEN:
        raise HTTPException(status_code=503, detail="GITHUB_TOKEN не настроен")
    path = (body.get("path") or "").strip()
    content = body.get("content") or ""
    message = (body.get("message") or f"Update {path}").strip()
    if not path:
        raise HTTPException(status_code=400, detail="Не указан путь")
    url = f"{GITHUB_API}/repos/{GITHUB_REPO}/contents/{path}"
    headers = {"Accept": "application/vnd.github+json", "Authorization": f"Bearer {GITHUB_TOKEN}"}
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
        return {"ok": True, "path": path, "branch": CODE_BRANCH,
                "commit_sha": data.get("commit", {}).get("sha"),
                "html_url": data.get("commit", {}).get("html_url")}

# ================= РЕЛИЗЫ =================

async def releases_list():
    data, _ = await _gh_get_sync(PATHS["releases"])
    return {"releases": data if isinstance(data, list) else []}

async def releases_save(body):
    releases = body.get("releases") or []
    if not isinstance(releases, list):
        raise HTTPException(status_code=400, detail="releases должен быть списком")
    await _gh_put_sync(PATHS["releases"], releases, "Update releases")
    return {"ok": True, "count": len(releases)}