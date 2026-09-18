# core_backend/routers/code_state.py
# /state — наблюдаемость цикла ABCD.
# Только события. Данные приходят снаружи.
from fastapi import APIRouter, Request
from datetime import datetime

router = APIRouter()

STATE = {
    "cycle": "ABCD",
    "phase": "idle",
    "modules": {},
    "events": [],
    "errors": [],
    "booted_at": None,
}

MAX_EVENTS = 40
MAX_ERRORS = 20


def _now():
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"


def _push(lst, item, cap):
    lst.insert(0, item)
    del lst[cap:]


@router.post("/state/event")
async def state_event(request: Request):
    body = await request.json()
    kind = body.get("kind")
    layer = body.get("layer")
    ok = body.get("ok")
    detail = body.get("detail")

    if layer and layer not in STATE["modules"]:
        STATE["modules"][layer] = {"status": "loaded", "mounted_at": _now()}

    _push(STATE["events"], {
        "t": _now(), "kind": kind, "layer": layer, "ok": ok, "detail": detail
    }, MAX_EVENTS)

    if ok is False:
        _push(STATE["errors"], {
            "t": _now(), "kind": kind, "layer": layer, "detail": detail
        }, MAX_ERRORS)

    return {"ok": True}


@router.get("/state")
async def state_get():
    return STATE


@router.post("/state/boot")
async def state_boot(request: Request):
    body = await request.json()
    STATE["phase"] = body.get("phase", "ready")
    STATE["booted_at"] = _now()
    return {"ok": True}