# app.py — точка входа Monolog.
# Отдаёт index.html, /chat, /code/*, /state, /cycles, /report, /render/*, /admin.

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

RENDER_API_KEY = os.getenv("RENDER_API_KEY", "").strip()
RENDER_API = "https://api.render.com/v1"

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


@app.get("/admin")
async def admin_page():
    return FileResponse("admin.html")


@app.get("/newbranch")
async def newbranch_page():
    return FileResponse("newbranch.html")


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "version": "structure-1.5",
        "branch": GITHUB_BRANCH,
        "github_ready": bool(GITHUB_TOKEN),
        "render_ready": bool(RENDER_API_KEY),
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
        return JSONResponse({"exists": False, "path": path, "content": ""}, status_code=404)
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
    return JSONResponse({"branch": ref, "total": len(paths), "ok": len(ok_list), "bad": bad_list})


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
    payload = {"message": f"delete {body.path} via Monolog", "sha": sha, "branch": ref}
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.request("DELETE", url, headers=_gh_headers(), json=payload)
    if r.status_code >= 400:
        raise HTTPException(status_code=502, detail=f"GitHub {r.status_code}: {r.text[:300]}")
    return JSONResponse({"ok": True, "path": body.path})


# --- ветки ---

class BranchCreate(BaseModel):
    name: str
    from_branch: str = ""


class BranchDelete(BaseModel):
    name: str


class BranchRename(BaseModel):
    old_name: str
    new_name: str


class ClearBranch(BaseModel):
    branch: str


@app.post("/code/branch-rename")
async def code_branch_rename(body: BranchRename):
    # проверить: не default ли ветка
    url_repo = f"{GITHUB_API}/repos/{GITHUB_REPO}"
    async with httpx.AsyncClient(timeout=30.0) as client:
        rr = await client.get(url_repo, headers=_gh_headers())
    default_branch = rr.json().get("default_branch", "main") if rr.status_code == 200 else "main"
    if body.old_name == default_branch:
        raise HTTPException(
            status_code=409,
            detail=f"'{body.old_name}' — default ветка. Смени default вручную на GitHub (Settings → Branches), потом переименовывай.",
        )
    # получить SHA старой ветки
    url_ref = f"{GITHUB_API}/repos/{GITHUB_REPO}/git/ref/heads/{body.old_name}"
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get(url_ref, headers=_gh_headers())
    if r.status_code != 200:
        raise HTTPException(status_code=502, detail=f"Ветка {body.old_name} не найдена")
    sha = r.json().get("object", {}).get("sha")
    # создать новую
    payload = {"ref": f"refs/heads/{body.new_name}", "sha": sha}
    async with httpx.AsyncClient(timeout=30.0) as client:
        r2 = await client.post(f"{GITHUB_API}/repos/{GITHUB_REPO}/git/refs",
                               headers=_gh_headers(), json=payload)
    if r2.status_code >= 400:
        raise HTTPException(status_code=502, detail=f"GitHub {r2.status_code}: {r2.text[:300]}")
    # удалить старую
    url_del = f"{GITHUB_API}/repos/{GITHUB_REPO}/git/refs/heads/{body.old_name}"
    async with httpx.AsyncClient(timeout=30.0) as client:
        r3 = await client.request("DELETE", url_del, headers=_gh_headers())
    if r3.status_code >= 400:
        raise HTTPException(status_code=502, detail=f"Создана {body.new_name}, но не удалена {body.old_name}")
    return JSONResponse({"ok": True, "from": body.old_name, "to": body.new_name})

@app.post("/code/branch-delete")
async def code_branch_delete(body: BranchDelete):
    # проверить: не default ли
    url_repo = f"{GITHUB_API}/repos/{GITHUB_REPO}"
    async with httpx.AsyncClient(timeout=30.0) as client:
        rr = await client.get(url_repo, headers=_gh_headers())
    default_branch = rr.json().get("default_branch", "main") if rr.status_code == 200 else "main"
    if body.name == default_branch:
        raise HTTPException(
            status_code=409,
            detail=f"'{body.name}' — default ветка. Сначала смени default вручную на GitHub (Settings → Branches).",
        )
    url = f"{GITHUB_API}/repos/{GITHUB_REPO}/git/refs/heads/{body.name}"
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.request("DELETE", url, headers=_gh_headers())
    if r.status_code >= 400:
        raise HTTPException(status_code=502, detail=f"GitHub {r.status_code}: {r.text[:300]}")
    return JSONResponse({"ok": True, "deleted": body.name})

@app.post("/code/branch-rename")
async def code_branch_rename(body: BranchRename):
    url_ref = f"{GITHUB_API}/repos/{GITHUB_REPO}/git/ref/heads/{body.old_name}"
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get(url_ref, headers=_gh_headers())
    if r.status_code != 200:
        raise HTTPException(status_code=502, detail=f"Ветка {body.old_name} не найдена")
    sha = r.json().get("object", {}).get("sha")
    payload = {"ref": f"refs/heads/{body.new_name}", "sha": sha}
    async with httpx.AsyncClient(timeout=30.0) as client:
        r2 = await client.post(f"{GITHUB_API}/repos/{GITHUB_REPO}/git/refs",
                               headers=_gh_headers(), json=payload)
    if r2.status_code >= 400:
        raise HTTPException(status_code=502, detail=f"GitHub {r2.status_code}: {r2.text[:300]}")
    url_del = f"{GITHUB_API}/repos/{GITHUB_REPO}/git/refs/heads/{body.old_name}"
    async with httpx.AsyncClient(timeout=30.0) as client:
        r3 = await client.request("DELETE", url_del, headers=_gh_headers())
    if r3.status_code >= 400:
        raise HTTPException(status_code=502, detail=f"Создана {body.new_name}, не удалена {body.old_name}")
    return JSONResponse({"ok": True, "from": body.old_name, "to": body.new_name})


@app.post("/code/clear")
async def code_clear(body: ClearBranch):
    url = f"{GITHUB_API}/repos/{GITHUB_REPO}/git/trees/{body.branch}"
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get(url, headers=_gh_headers(), params={"recursive": "1"})
    if r.status_code >= 400:
        raise HTTPException(status_code=502, detail=f"GitHub {r.status_code}")
    tree = r.json().get("tree", [])
    paths = [i["path"] for i in tree if i.get("type") == "blob"]
    deleted = []
    errors = []
    async with httpx.AsyncClient(timeout=30.0) as client:
        for p in paths:
            ur = f"{GITHUB_API}/repos/{GITHUB_REPO}/contents/{p}"
            rr = await client.get(ur, headers=_gh_headers(), params={"ref": body.branch})
            if rr.status_code != 200:
                errors.append({"path": p, "status": rr.status_code})
                continue
            sha = rr.json().get("sha")
            payload = {"message": f"clear {p}", "sha": sha, "branch": body.branch}
            rd = await client.request("DELETE", ur, headers=_gh_headers(), json=payload)
            if rd.status_code < 400:
                deleted.append(p)
            else:
                errors.append({"path": p, "status": rd.status_code})
    return JSONResponse({"ok": True, "branch": body.branch,
                         "total": len(paths), "deleted": len(deleted), "errors": errors[:20]})

class BranchCopy(BaseModel):
    from_branch: str
    to_branch: str
    overwrite: bool = True


@app.post("/code/branch-copy")
async def code_branch_copy(body: BranchCopy):
    # 1. дерево источника
    url = f"{GITHUB_API}/repos/{GITHUB_REPO}/git/trees/{body.from_branch}"
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get(url, headers=_gh_headers(), params={"recursive": "1"})
    if r.status_code >= 400:
        raise HTTPException(status_code=502, detail=f"Ветка {body.from_branch} не найдена: {r.status_code}")
    tree = r.json().get("tree", [])
    paths = [i["path"] for i in tree if i.get("type") == "blob"]

    copied = []
    skipped = []
    errors = []

    async with httpx.AsyncClient(timeout=30.0) as client:
        for p in paths:
            # читать файл из источника
            ur = f"{GITHUB_API}/repos/{GITHUB_REPO}/contents/{p}"
            rr = await client.get(ur, headers=_gh_headers(), params={"ref": body.from_branch})
            if rr.status_code != 200:
                errors.append({"path": p, "stage": "read", "status": rr.status_code})
                continue
            data = rr.json()
            content_b64 = data.get("content", "")

            # проверить, есть ли файл в приёмнике
            rt = await client.get(ur, headers=_gh_headers(), params={"ref": body.to_branch})
            sha_target = rt.json().get("sha") if rt.status_code == 200 else None

            if sha_target and not body.overwrite:
                skipped.append(p)
                continue

            # записать
            payload = {
                "message": f"copy {p} from {body.from_branch} to {body.to_branch}",
                "content": content_b64,
                "branch": body.to_branch,
            }
            if sha_target:
                payload["sha"] = sha_target
            rw = await client.put(ur, headers=_gh_headers(), json=payload)
            if rw.status_code < 400:
                copied.append(p)
            else:
                errors.append({"path": p, "stage": "write", "status": rw.status_code})

    return JSONResponse({
        "ok": True,
        "from": body.from_branch,
        "to": body.to_branch,
        "total": len(paths),
        "copied": len(copied),
        "skipped": len(skipped),
        "errors": errors[:20],
    })

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


# --- /cycles ---

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


# --- /report ---

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
        "t": body.t, "level": body.level,
        "cycles_done": body.cycles_done, "went_to": body.went_to,
        "last_result": body.last_result,
        "emergency": body.emergency, "reason": body.reason,
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
    from urllib.parse import quote
    r = await _gh_get(quote("Стартер"), GITHUB_BRANCH)
    if r.status_code != 200:
        raise HTTPException(status_code=404, detail="Файл Стартер не найден")
    try:
        prompt = base64.b64decode(r.json().get("content", "")).decode("utf-8")
    except Exception:
        raise HTTPException(status_code=502, detail="Не удалось прочитать Стартер")
    key = next_dev_key()
    if not key:
        raise HTTPException(status_code=503, detail="Нет ключей")
    state_json = json.dumps(STATE, ensure_ascii=False)[:2000]
    try:
        async with httpx.AsyncClient(timeout=180.0) as client:
            rr = await client.post(
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
        data = rr.json()
        reply = data["choices"][0]["message"]["content"]
        STATE["events"].insert(0, {"kind": "start", "layer": "A", "ok": True, "detail": reply[:200]})
        del STATE["events"][40:]
        return JSONResponse({"ok": True, "reply": reply})
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Ошибка ИИ: {e}")


# --- /render (управление Render) ---

def _rnd_headers():
    return {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Authorization": f"Bearer {RENDER_API_KEY}",
    }


class RenderCreate(BaseModel):
    name: str
    branch: str
    repo: str = "https://github.com/ekhusyainova-blip/monolog"
    env_group_id: Optional[str] = None
    owner_id: Optional[str] = None
    region: str = "frankfurt"
    plan: str = "free"
    build_command: str = ""
    start_command: str = "uvicorn app:app --host 0.0.0.0 --port $PORT"
    python_version: str = "3.11.9"


@app.post("/render/create")
async def render_create(body: RenderCreate):
    if not RENDER_API_KEY:
        raise HTTPException(status_code=503, detail="RENDER_API_KEY не задан")
    payload = {
        "type": "web_service",
        "name": body.name,
        "ownerId": body.owner_id or "self",
        "repo": body.repo,
        "branch": body.branch,
        "autoDeploy": "yes",
        "envVars": [],
        "serviceDetails": {
            "env": "python",
            "plan": body.plan,
            "region": body.region,
            "healthCheckPath": "/health",
            "envSpecificDetails": {
                "buildCommand": body.build_command or "pip install -r requirements.txt",
                "startCommand": body.start_command,
                "pythonVersion": body.python_version,
            },
        },
    }
    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.post(f"{RENDER_API}/services", headers=_rnd_headers(), json=payload)
    if r.status_code >= 400:
        raise HTTPException(status_code=502, detail=f"Render {r.status_code}: {r.text[:400]}")
    data = r.json()
    service = data.get("service", data)
    service_id = service.get("id")
    group_ok = False
    if body.env_group_id and service_id:
        async with httpx.AsyncClient(timeout=30.0) as client:
            rr = await client.post(
                f"{RENDER_API}/env-groups/{body.env_group_id}/services/{service_id}",
                headers=_rnd_headers(),
            )
        group_ok = rr.status_code < 400
    return JSONResponse({
        "ok": True, "service_id": service_id,
        "name": service.get("name"), "branch": body.branch,
        "url": service.get("serviceDetails", {}).get("url", ""),
        "env_group_linked": group_ok,
    })


@app.post("/render/env-link")
async def render_env_link(group_id: str, service_id: str):
    if not RENDER_API_KEY:
        raise HTTPException(status_code=503, detail="RENDER_API_KEY не задан")
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post(
            f"{RENDER_API}/env-groups/{group_id}/services/{service_id}",
            headers=_rnd_headers(),
        )
    if r.status_code >= 400:
        raise HTTPException(status_code=502, detail=f"Render {r.status_code}: {r.text[:400]}")
    return {"ok": True, "group": group_id, "service": service_id}


@app.post("/render/env-set-group")
async def render_env_set_group(group_id: str, key: str, value: str):
    if not RENDER_API_KEY:
        raise HTTPException(status_code=503, detail="RENDER_API_KEY не задан")
    payload = {"envVars": [{"key": key, "value": value}]}
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.put(
            f"{RENDER_API}/env-groups/{group_id}",
            headers=_rnd_headers(), json=payload,
        )
    if r.status_code >= 400:
        raise HTTPException(status_code=502, detail=f"Render {r.status_code}: {r.text[:400]}")
    return {"ok": True, "group": group_id, "key": key}


@app.post("/render/env-set-service")
async def render_env_set_service(service_id: str, key: str, value: str):
    if not RENDER_API_KEY:
        raise HTTPException(status_code=503, detail="RENDER_API_KEY не задан")
    payload = {"envVars": [{"key": key, "value": value}]}
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.put(
            f"{RENDER_API}/services/{service_id}/env-vars",
            headers=_rnd_headers(), json=payload,
        )
    if r.status_code >= 400:
        raise HTTPException(status_code=502, detail=f"Render {r.status_code}: {r.text[:400]}")
    return {"ok": True, "service": service_id, "key": key}


@app.get("/render/services")
async def render_services():
    if not RENDER_API_KEY:
        raise HTTPException(status_code=503, detail="RENDER_API_KEY не задан")
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get(f"{RENDER_API}/services", headers=_rnd_headers())
    if r.status_code >= 400:
        raise HTTPException(status_code=502, detail=f"Render {r.status_code}: {r.text[:400]}")
    return JSONResponse(r.json())


@app.get("/render/env-groups")
async def render_env_groups():
    if not RENDER_API_KEY:
        raise HTTPException(status_code=503, detail="RENDER_API_KEY не задан")
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get(f"{RENDER_API}/env-groups", headers=_rnd_headers())
    if r.status_code >= 400:
        raise HTTPException(status_code=502, detail=f"Render {r.status_code}: {r.text[:400]}")
    return JSONResponse(r.json())


@app.get("/render/owner")
async def render_owner():
    if not RENDER_API_KEY:
        raise HTTPException(status_code=503, detail="RENDER_API_KEY не задан")
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get(f"{RENDER_API}/owners", headers=_rnd_headers())
    if r.status_code >= 400:
        raise HTTPException(status_code=502, detail=f"Render {r.status_code}: {r.text[:400]}")
    return JSONResponse(r.json())


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=int(os.getenv("PORT", 8000)))