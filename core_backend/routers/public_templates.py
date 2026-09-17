# core_backend/routers/public_templates.py
# Публичные шаблоны. APIRouter.

import time
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse

from core_backend.config import (
    PUBLIC_TEMPLATES_PATH,
    PUBLIC_REPUTATION_PATH,
)
from core_backend.github_api import github_get_json, github_put_json


router = APIRouter(prefix="/public", tags=["public-templates"])


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
        raise HTTPException(status_code=400, detail="Тело должно быть объектом")
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
    await github_put_json(PUBLIC_TEMPLATES_PATH, items, "Public: template publish")

    rep, _ = await github_get_json(PUBLIC_REPUTATION_PATH)
    rep = rep if isinstance(rep, dict) else {}
    user_rep = rep.get(uid) or {"given": 0, "taken": 0, "help_score": 0}
    user_rep["given"] = (user_rep.get("given") or 0) + 1
    rep[uid] = user_rep
    await github_put_json(PUBLIC_REPUTATION_PATH, rep, "Reputation: +given")

    return JSONResponse({"ok": True, "template": new_item})