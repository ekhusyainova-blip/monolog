# core_backend/routers/debug_syntax.py
# Проверка синтаксиса JS и JSON.

import os
import json

from fastapi import APIRouter
from fastapi.responses import JSONResponse


router = APIRouter(prefix="/debug/syntax", tags=["debug-syntax"])


def _js_quick_check(text: str):
    stack = []
    in_str = None
    escape = False
    line = 1
    for ch in text:
        if ch == "\n":
            line += 1
        if escape:
            escape = False
            continue
        if ch == "\\" and in_str:
            escape = True
            continue
        if in_str:
            if ch == in_str:
                in_str = None
            continue
        if ch in ("'", '"', "`"):
            in_str = ch
            continue
        if ch in "({[":
            stack.append((ch, line))
        elif ch in ")}]":
            if not stack:
                return {"ok": False, "error": f"лишняя {ch}", "line": line}
            open_ch, open_line = stack.pop()
            pair = {"(": ")", "[": "]", "{": "}"}
            if pair[open_ch] != ch:
                return {"ok": False,
                        "error": f"несоответствие {open_ch} ({open_line}) и {ch}",
                        "line": line}
    if stack:
        return {"ok": False, "error": f"незакрытая {stack[-1][0]}", "line": stack[-1][1]}
    if in_str:
        return {"ok": False, "error": f"незакрытая кавычка {in_str}"}
    return {"ok": True}


@router.get("/js")
async def syntax_js(path: str):
    if not os.path.exists(path):
        return JSONResponse({"exists": False, "path": path})
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()
    result = _js_quick_check(content)
    result.update({"exists": True, "path": path, "size": len(content)})
    return JSONResponse(result)


@router.get("/json")
async def syntax_json(path: str):
    if not os.path.exists(path):
        return JSONResponse({"exists": False, "path": path})
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()
    try:
        data = json.loads(content)
        return JSONResponse({
            "exists": True, "path": path, "valid": True,
            "keys_count": len(data) if isinstance(data, dict) else "not_dict",
        })
    except Exception as e:
        return JSONResponse({"exists": True, "path": path, "valid": False, "error": str(e)})


@router.get("/js_all")
async def js_all():
    results = []
    for folder in ["core", "adaptive"]:
        if not os.path.exists(folder):
            continue
        for name in os.listdir(folder):
            if not name.endswith(".js"):
                continue
            p = f"{folder}/{name}"
            with open(p, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            r = _js_quick_check(content)
            r.update({"path": p})
            results.append(r)
    return JSONResponse({"files": results})


@router.get("/json_all")
async def json_all():
    results = []
    for folder in ["adaptive", "public", "blog"]:
        if not os.path.exists(folder):
            continue
        for name in os.listdir(folder):
            if not name.endswith(".json"):
                continue
            p = f"{folder}/{name}"
            with open(p, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            try:
                json.loads(content)
                results.append({"path": p, "valid": True})
            except Exception as e:
                results.append({"path": p, "valid": False, "error": str(e)})
    return JSONResponse({"files": results})