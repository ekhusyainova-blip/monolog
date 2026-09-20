# app.py — точка входа Monolog.
# Отдаёт index.html, /chat, /code/*, /state, /cycles.

import os
import sys
import json
import base64
import logging
from typing import List, Optional

import httpx
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

sys.path.insert(0, os.path.dirname(__file__))
from A_papka import A_file as A_AF
from B_papka import B_file as B_BF
from C_papka import C_file as C_CF
from D_papka import D_file as D_DF

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("monolog")

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "").strip()
GITHUB_REPO = os.getenv("GITHUB_REPO", "ekhusyainova-blip/monolog").strip()
GITHUB_BRANCH = os.getenv("GITHUB_BRANCH", "structure").strip()
GITHUB_API = "https://api.github.com"

_DEV_KEYS_GROQ: List[str] = [
    k.strip() for k in os.getenv("GROQ_API_KEYS", "").split(",") if k.strip()
]
_dev_key_idx = [0]


def next_dev_key() -> Optional[str]:
    if not _DEV_KEYS_GROQ:
        return None
    k = _DEV_KEYS_GROQ[_dev_key_idx[0] % len(_DEV_KEYS_GROQ)]
    _dev_key_idx[0] += 1
    return k


app = FastAPI(title="Monolog (structure)")
app.mount("/core", StaticFiles(directory="core"), name="core")
app.mount("/adaptive", StaticFiles(directory="adaptive"), name="adaptive")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)


@app.get("/")
async def root():
    return FileResponse("index.html")


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "version": "structure-1.4",
        "branch": GITHUB_BRANCH,
        "github_ready": bool(GITHUB_TOKEN),
        "groq_keys": len(_DEV_KEYS_GROQ),
    }


@app.get("/ui")
async def ui():
    data = {"input": {"hello": "world"}}
    return JSONResponse({
        "a": A_AF.a_fragment(data), "b": B_BF.b_fragment(data),
        "c": C_CF.c_fragment(data), "d": D_DF.d_fragment(data),
    })


class ChatRequest(BaseModel):
    message: str = ""


@app.post("/chat")
async def chat(body: ChatRequest):
    msg = (body.message or "").strip()
    if not msg:
        raise HTTPException(status_code=400, detail="Пустое сообщение")
    key = next_dev_key()
    if not key:
        raise HTTPException(status_code=503, detail="Нет ключей")
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            r = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json={
                    "model": "openai/gpt-oss-20b",
                    "messages": [
                        {"role": "system", "content": "Ты — Monolog. Когнитивный партнёр."},
                        {"role": "user", "content": msg},
                    ],
                    "max_tokens": 1500,
                },
            )
        reply = r.json()["choices"][0]["message"]["content"]
        return JSONResponse({"reply_text": reply})
    except Exception as e:
        return JSONResponse({"reply_text": f"Ошибка: {e}"})


# --- GitHub helpers ---

def _gh_headers():
    h = {"Accept": "application/vnd.github+json"}
    if GITHUB_TOKEN:
        h["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    return h


async def _gh_get(path: str, ref: str = ""):
    url = f"{GITHUB_API}/repos/{GITHUB_REPO}/{path}"
    params = {"ref": ref or GITHUB_BRANCH}
    async with httpx.AsyncClient(timeout=30.0) as client:
        return await client.get(url, headers=_gh_headers(), params=params)


@app.get("/code/tree")
async def code_tree(branch: str = ""):
    ref = branch or GITHUB_BRANCH
    url = f"{GITHUB_API}/repos/{GITHUB_REPO}/git/trees/{ref}"
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get(url, headers=_gh_headers(), params={"recursive": "1"})
    if r.status_code >= 400:
        raise HTTPException(status_code=502, detail=f"GitHub: {r.status_code}")
    tree = r.json().get("tree", [])
    paths = [i["path"] for i in tree if i.get("type") == "blob"]
    return JSONResponse({"branch": ref, "count": len(paths), "paths": paths[:500]})


@app.get("/code/branches")
async def code_branches():
    url = f"{GITHUB_API}/repos/{GITHUB_REPO}/branches"
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get(url, headers=_gh_headers())
    if r.status_code >= 400:
        raise HTTPException(status_code=502, detail=f"GitHub: {r.status_code}")
    names = [b.get("name") for b in r.json()]
    return JSONResponse({"branches": names, "count": len(names)})


@app.get("/code/read")
async def code_read(path: str, branch: str = ""):
    r = await _gh_get(f"contents/{path}", branch)
    if r.status_code == 404:
        return JSONResponse(
            {"exists": False, "path": path, "content": ""},
            status_code=404,
        )
    if r.status_code >= 400:
        raise HTTPException(status_code=502, detail=f"GitHub: {r.status_code}")
    data = r.json()
    try:
        content = base64.b64decode(data.get("content", "")).decode("utf-8")
    except Exception:
        content = ""
    return JSONResponse({"exists": True, "path": path, "sha": data.get("sha"), "content": content})


class SaveRequest(BaseModel):
    branch: str = ""
    path: str
    content: str
    sha: Optional[str] = None


@app.post("/code/save")
async def code_save(body: SaveRequest):
    ref = body.branch or GITHUB_BRANCH
    url = f"{GITHUB_API}/repos/{GITHUB_REPO}/contents/{body.path}"
    sha = body.sha
    if not sha:
        r0 = await _gh_get(f"contents/{body.path}", ref)
        if r0.status_code == 200:
            sha = r0.json().get("sha")
    payload = {
        "message": f"save {body.path} via Monolog",
        "content": base64.b64encode(body.content.encode("utf-8")).decode("ascii"),
        "branch": ref,
    }
    if sha:
        payload["sha"] = sha
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.put(url, headers=_gh_headers(), json=payload)
    if r.status_code >= 400:
        raise HTTPException(status_code=502, detail=f"GitHub {r.status_code}: {r.text[:300]}")
    return JSONResponse({"ok": True, "path": body.path,
                         "sha": r.json().get("content", {}).get("sha")})


class CheckRequest(BaseModel):
    branch: str = ""
    path: str


@app.post("/code/check")
async def code_check(body: CheckRequest):
    ref = body.branch or GITHUB_BRANCH
    r = await _gh_get(f"contents/{body.path}", ref)
    return JSONResponse({"path": body.path, "branch": ref,
                         "exists": r.status_code == 200, "status": r.status_code})


class CheckAllRequest(BaseModel):
    branch: str = ""
    limit: int = 500


@app.post("/code/check-all")
async def code_check_all(body: CheckAllRequest):
    ref = body.branch or GITHUB_BRANCH
    url = f"{GITHUB_API}/repos/{GITHUB_REPO}/git/trees/{ref}"
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get(url, headers=_gh_headers(), params={"recursive": "1"})
    if r.status_code >= 400:
        raise HTTPException(status_code=502, detail=f"GitHub: {r.status_code}")
    tree = r.json().get("tree", [])
    paths = [i["path"] for i in tree if i.get("type") == "blob"][:body.limit]

    ok_list = []
    bad_list = []
    async with httpx.AsyncClient(timeout=30.0) as client:
        for p in paths:
            u = f"{GITHUB_API}/repos/{GITHUB_REPO}/contents/{p}"
            rr = await client.get(u, headers=_gh_headers(), params={"ref": ref})
            if rr.status_code == 200:
                ok_list.append(p)
            else:
                bad_list.append({"path": p, "status": rr.status_code})

    return JSONResponse({
        "branch": ref,
        "total": len(paths),
        "ok": len(ok_list),
        "bad": bad_list,
    })

class CreateRequest(BaseModel):
    branch: str = ""
    path: str
    content: str = ""


@app.post("/code/create")
async def code_create(body: CreateRequest):
    ref = body.branch or GITHUB_BRANCH
    url = f"{GITHUB_API}/repos/{GITHUB_REPO}/contents/{body.path}"
    payload = {
        "message": f"create {body.path} via Monolog",
        "content": base64.b64encode(body.content.encode("utf-8")).decode("ascii"),
        "branch": ref,
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.put(url, headers=_gh_headers(), json=payload)
    if r.status_code == 422:
        raise HTTPException(status_code=409, detail="Файл уже существует")
    if r.status_code >= 400:
        raise HTTPException(status_code=502, detail=f"GitHub {r.status_code}: {r.text[:300]}")
    return JSONResponse({"ok": True, "path": body.path})


class DeleteRequest(BaseModel):
    branch: str = ""
    path: str


@app.post("/code/delete")
async def code_delete(body: DeleteRequest):
    ref = body.branch or GITHUB_BRANCH
    r0 = await _gh_get(f"contents/{body.path}", ref)
    if r0.status_code != 200:
        raise HTTPException(status_code=404, detail="Файл не найден")
    sha = r0.json().get("sha")
    url = f"{GITHUB_API}/repos/{GITHUB_REPO}/contents/{body.path}"
    payload = {"message": f"delete {body.path} via Monolog",
               "sha": sha, "branch": ref}
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.request("DELETE", url, headers=_gh_headers(), json=payload)
    if r.status_code >= 400:
        raise HTTPException(status_code=502, detail=f"GitHub {r.status_code}: {r.text[:300]}")
    return JSONResponse({"ok": True, "path": body.path})


# --- /state ---

STATE = {"schema": "ABCD", "phase": "idle", "modules": {},
         "events": [], "errors": [], "booted_at": None}


@app.get("/state")
async def state_get():
    return STATE


@app.post("/state/event")
async def state_event(request: Request):
    body = await request.json()
    layer = body.get("layer")
    if layer and layer not in STATE["modules"]:
        STATE["modules"][layer] = {"status": "loaded"}
    STATE["events"].insert(0, {
        "kind": body.get("kind"), "layer": layer,
        "ok": body.get("ok"), "detail": body.get("detail"),
    })
    del STATE["events"][40:]
    if body.get("ok") is False:
        STATE["errors"].insert(0, body)
        del STATE["errors"][20:]
    return {"ok": True}


@app.post("/state/boot")
async def state_boot(request: Request):
    body = await request.json()
    STATE["phase"] = body.get("phase", "ready")
    from datetime import datetime
    STATE["booted_at"] = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    return {"ok": True}


# --- /cycles (Журнал) ---

def _cycles_path():
    return "public/cycles.json"


async def _load_cycles():
    r = await _gh_get(_cycles_path(), GITHUB_BRANCH)
    if r.status_code != 200:
        return {"cycles": []}
    try:
        content = base64.b64decode(r.json().get("content", "")).decode("utf-8")
        return json.loads(content)
    except Exception:
        return {"cycles": []}


@app.get("/cycles")
async def cycles_get():
    return await _load_cycles()


class CycleAdd(BaseModel):
    n: int
    date: str = ""
    summary: str = ""
    tags: List[str] = []
    status: str = "closed"


@app.post("/cycles/add")
async def cycles_add(body: CycleAdd):
    data = await _load_cycles()
    cycles = data.get("cycles", [])
    cycles = [c for c in cycles if c.get("n") != body.n]
    cycles.insert(0, {
        "n": body.n, "date": body.date or "",
        "summary": body.summary, "tags": body.tags, "status": body.status,
    })
    data["cycles"] = cycles[:200]
    ref = GITHUB_BRANCH
    r0 = await _gh_get(_cycles_path(), ref)
    sha = r0.json().get("sha") if r0.status_code == 200 else None
    payload = {
        "message": f"cycle {body.n} — {body.summary[:60]}",
        "content": base64.b64encode(
            json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        ).decode("ascii"),
        "branch": ref,
    }
    if sha:
        payload["sha"] = sha
    url = f"{GITHUB_API}/repos/{GITHUB_REPO}/contents/{_cycles_path()}"
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.put(url, headers=_gh_headers(), json=payload)
    if r.status_code >= 400:
        raise HTTPException(status_code=502, detail=f"GitHub {r.status_code}: {r.text[:300]}")
    return JSONResponse({"ok": True, "n": body.n})

# --- /report (от стартера) ---

REPORTS = []


class ReportBody(BaseModel):
    t: str = ""
    level: str = ""
    cycles_done: int = 0
    went_to: str = ""
    last_result: str = ""
    emergency: bool = False
    reason: str = ""


@app.post("/report")
async def report_add(body: ReportBody):
    entry = {
        "t": body.t,
        "level": body.level,
        "cycles_done": body.cycles_done,
        "went_to": body.went_to,
        "last_result": body.last_result,
        "emergency": body.emergency,
        "reason": body.reason,
    }
    REPORTS.insert(0, entry)
    del REPORTS[200:]

    if body.emergency:
        STATE["errors"].insert(0, entry)
        del STATE["errors"][20:]

    return {"ok": True}


@app.get("/reports")
async def reports_get():
    return {"reports": REPORTS}
    
    # --- /start (запуск стартера) ---

@app.get("/start")
async def start_cycle():
    # читаем файл Стартер из репозитория
    from urllib.parse import quote
    r = await _gh_get(quote("Стартер"), GITHUB_BRANCH)
    if r.status_code != 200:
        raise HTTPException(status_code=404, detail="Файл Стартер не найден")
    try:
        prompt = base64.b64decode(r.json().get("content", "")).decode("utf-8")
    except Exception:
        raise HTTPException(status_code=502, detail="Не удалось прочитать Стартер")

    # берём ключ
    key = next_dev_key()
    if not key:
        raise HTTPException(status_code=503, detail="Нет ключей")

    # состояние для контекста
    state_json = json.dumps(STATE, ensure_ascii=False)[:2000]

    try:
        async with httpx.AsyncClient(timeout=180.0) as client:
            r = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json={
                    "model": "openai/gpt-oss-20b",
                    "messages": [
                        {"role": "system", "content": prompt},
                        {"role": "user", "content": "Состояние: " + state_json},
                    ],
                    "max_tokens": 2000,
                },
            )
        data = r.json()
        reply = data["choices"][0]["message"]["content"]
        STATE["events"].insert(0, {
            "kind": "start", "layer": "A", "ok": True,
            "detail": reply[:200],
        })
        del STATE["events"][40:]
        return JSONResponse({"ok": True, "reply": reply})
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Ошибка ИИ: {e}")

# --- создание ветки ---

class BranchCreate(BaseModel):
    name: str
    from_branch: str = ""


@app.post("/code/branch-create")
async def code_branch_create(body: BranchCreate):
    from_ref = body.from_branch or GITHUB_BRANCH
    # 1. получить sha базовой ветки
    url_ref = f"{GITHUB_API}/repos/{GITHUB_REPO}/git/ref/heads/{from_ref}"
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get(url_ref, headers=_gh_headers())
    if r.status_code != 200:
        raise HTTPException(
            status_code=502,
            detail=f"Не найдена ветка {from_ref}: {r.status_code}",
        )
    sha = r.json().get("object", {}).get("sha")
    if not sha:
        raise HTTPException(status_code=502, detail="Не получен SHA базовой ветки")

    # 2. создать новую ветку
    url_create = f"{GITHUB_API}/repos/{GITHUB_REPO}/git/refs"
    payload = {"ref": f"refs/heads/{body.name}", "sha": sha}
    async with httpx.AsyncClient(timeout=30.0) as client:
        r2 = await client.post(url_create, headers=_gh_headers(), json=payload)
    if r2.status_code == 422:
        raise HTTPException(status_code=409, detail="Ветка уже существует")
    if r2.status_code >= 400:
        raise HTTPException(
            status_code=502,
            detail=f"GitHub {r2.status_code}: {r2.text[:300]}",
        )
    return JSONResponse({"ok": True, "branch": body.name, "from": from_ref, "sha": sha})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=int(os.getenv("PORT", 8000)))