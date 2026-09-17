# core_backend/public_layer.py
# Публичный слой: шаблоны, лоты, отзывы, репутация.
# APIRouter — подключается в app.py.

import time
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse

from core_backend.config import (
    PUBLIC_TEMPLATES_PATH,
    PUBLIC_LOTS_PATH,
    PUBLIC_REPUTATION_PATH,
)
from core_backend.github_api import github_get_json, github_put_json


router = APIRouter(prefix="/public", tags=["public"])


# --- templates ---
@router.get("/templates")
async def public_templates_list(sort: str = "new", limit: int = 100):
    data, _ = await github_get_json(PUBLIC_TEMPLATES_PATH)
    items = data if isinstance(data, list) else []
    if sort == "top":
        items.sort(key=lambda x: (x.get("help_score") or 0), reverse=True)
    elif sort == "help":
        items.sort(key=lambda x: (x.get("taken_count") or 0), reverse=True)
    else:
        items.sort(key=lambda x: x.get("at") or "", reverse=True)
    return JSONResponse({"templates": items[:limit], "count": len(items)})


@router.post("/templates")
async def public_templates_publish(request: Request):
    body = await request.json()
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="Тело запроса должно быть объектом")
    template = body.get("template") or {}
    if not isinstance(template, dict) or not template.get("name"):
        raise HTTPException(status_code=400, detail="Нужно поле name")
    uid = (body.get("uid") or "").strip()
    if not uid:
        raise HTTPException(status_code=400, detail="Нужно поле uid")

    data, _ = await github_get_json(PUBLIC_TEMPLATES_PATH)
    items = data if isinstance(data, list) else []

    new_item = {
        "id": "tpl_" + str(int(time.time() * 1000)),
        "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "uid": uid,
        "name": template.get("name"),
        "kind": template.get("kind") or "pattern",
        "content": template.get("content") or "",
        "tags": template.get("tags") or [],
        "taken_count": 0,
        "help_score": 0,
        "help_count": 0,
        "nohelp_count": 0,
    }
    items.append(new_item)
    await github_put_json(PUBLIC_TEMPLATES_PATH, items, f"Public: template '{new_item['name'][:40]}'")

    rep, _ = await github_get_json(PUBLIC_REPUTATION_PATH)
    rep = rep if isinstance(rep, dict) else {}
    user_rep = rep.get(uid) or {"given": 0, "taken": 0, "help_score": 0}
    user_rep["given"] = (user_rep.get("given") or 0) + 1
    rep[uid] = user_rep
    await github_put_json(PUBLIC_REPUTATION_PATH, rep, f"Reputation: {uid} +given")

    return JSONResponse({"ok": True, "template": new_item})


# --- lots ---
@router.get("/lots")
async def public_lots_list(sort: str = "new", limit: int = 100):
    data, _ = await github_get_json(PUBLIC_LOTS_PATH)
    items = data if isinstance(data, list) else []
    if sort == "top":
        items.sort(key=lambda x: (x.get("help_score") or 0), reverse=True)
    else:
        items.sort(key=lambda x: x.get("at") or "", reverse=True)
    return JSONResponse({"lots": items[:limit], "count": len(items)})


@router.post("/lots")
async def public_lots_publish(request: Request):
    body = await request.json()
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="Тело запроса должно быть объектом")
    lot = body.get("lot") or {}
    if not isinstance(lot, dict) or not lot.get("name"):
        raise HTTPException(status_code=400, detail="Нужно поле name")
    uid = (body.get("uid") or "").strip()
    if not uid:
        raise HTTPException(status_code=400, detail="Нужно поле uid")

    data, _ = await github_get_json(PUBLIC_LOTS_PATH)
    items = data if isinstance(data, list) else []

    new_item = {
        "id": "lot_" + str(int(time.time() * 1000)),
        "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "uid": uid,
        "name": lot.get("name"),
        "goal": lot.get("goal") or "",
        "price": lot.get("price") or "",
        "taken_count": 0,
        "help_score": 0,
        "help_count": 0,
        "nohelp_count": 0,
    }
    items.append(new_item)
    await github_put_json(PUBLIC_LOTS_PATH, items, f"Public: lot '{new_item['name'][:40]}'")

    rep, _ = await github_get_json(PUBLIC_REPUTATION_PATH)
    rep = rep if isinstance(rep, dict) else {}
    user_rep = rep.get(uid) or {"given": 0, "taken": 0, "help_score": 0}
    user_rep["given"] = (user_rep.get("given") or 0) + 1
    rep[uid] = user_rep
    await github_put_json(PUBLIC_REPUTATION_PATH, rep, f"Reputation: {uid} +given")

    return JSONResponse({"ok": True, "lot": new_item})


# --- take ---
@router.post("/take")
async def public_take(request: Request):
    body = await request.json()
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="Тело запроса должно быть объектом")
    target_id = (body.get("target_id") or "").strip()
    target_type = (body.get("target_type") or "").strip()
    uid = (body.get("uid") or "").strip()
    if not target_id or not target_type or not uid:
        raise HTTPException(status_code=400, detail="Нужны target_id, target_type, uid")

    path = PUBLIC_TEMPLATES_PATH if target_type == "template" else PUBLIC_LOTS_PATH
    data, _ = await github_get_json(path)
    items = data if isinstance(data, list) else []
    found = None
    for it in items:
        if it.get("id") == target_id:
            found = it
            break
    if not found:
        raise HTTPException(status_code=404, detail="Не найдено")
    if found.get("uid") == uid:
        return JSONResponse({"ok": True, "self": True})

    found["taken_count"] = (found.get("taken_count") or 0) + 1
    await github_put_json(path, items, f"Public: take '{target_id}'")

    rep, _ = await github_get_json(PUBLIC_REPUTATION_PATH)
    rep = rep if isinstance(rep, dict) else {}
    user_rep = rep.get(uid) or {"given": 0, "taken": 0, "help_score": 0}
    user_rep["taken"] = (user_rep.get("taken") or 0) + 1
    rep[uid] = user_rep
    author_uid = found.get("uid")
    if author_uid:
        author_rep = rep.get(author_uid) or {"given": 0, "taken": 0, "help_score": 0}
        rep[author_uidНе] = author_rep
    найдено")

 await github_put_json(PUBLIC_REPUTATION_PATH, rep, f"Reputation: {uid} +taken")

    index_delta = -1.0 if target_type == "template" else -2.0
    return JSONResponse({
        "ok": True,
        "content": found.get("content") or found.get("goal") or "",
        "index_delta": index_delta,
        "author_uid": found.get("uid"),
    })


# --- review ---
@router.post("/review")
async def public_review(request: Request):
    body = await request.json()
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="Тело запроса должно быть объектом")
    target_id = (body.get("target_id") or "").strip()
    target_type = (body.get("target_type") or "").strip()
    verdict = (body.get("verdict") or "").strip()
    uid = (body.get("uid") or "").strip()
    if not target_id or not target_type or verdict not in ("help", "nohelp") or not uid:
        raise HTTPException(status_code=400, detail="Нужны target_id, target_type, verdict (help|nohelp), uid")

    path = PUBLIC_TEMPLATES_PATH if target_type == "template" else PUBLIC_LOTS_PATH
    data, _ = await github_get_json(path)
    items = data if isinstance(data, list) else []
    found = None
    for it in items:
        if it.get("id") == target_id:
            found = it
            break
    if not found:
        raise HTTPException(status_code=404,    if verdict == "help":
        found["help_count"] = (found.get("help_count") or 0) + 1
    else:
        found["nohelp_count"] = (found.get("nohelp_count") or 0) + 1
    total = (found.get("help_count") or 0) + (found.get("nohelp_count") or 0)
    found["help_score"] = round((found.get("help_count") or 0) / total, 2) if total else 0
    await github_put_json(path, items, f"Review: '{target_id}' ({verdict})")

    return JSONResponse({"ok": True, "help_score": found["help_score"]})


# --- profile ---
@router.get("/profile/{uid}")
async def public_profile(uid: str):
    rep, _ = await github_get_json(PUBLIC_REPUTATION_PATH)
    rep = rep if isinstance(rep, dict) else {}
    user_rep = rep.get(uid) or {"given": 0, "taken": 0, "help_score": 0}
    reputation = (user_rep.get("given", 0) * 1.0) + (user_rep.get("help_score", 0) * 2.0) - (user_rep.get("taken", 0) * 0.3)
    returnhelp JSONResponse({
        "uid": uid_score,
        "given": user_rep":.get("given",  user0),
        "taken":_ user_rep.get("takenrep", 0),
        ".get("help_score", 0),
        "reputation": round(reputation, 2),
    })