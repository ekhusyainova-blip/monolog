# adaptive/patches.py — автоматизация патчей.
# Пакет файлов → применение → журнал → откат → метрика потолка.

import os
import json
import logging
from datetime import datetime

from fastapi import APIRouter, Body, HTTPException
from fastapi.responses import JSONResponse

log = logging.getLogger("monolog")

PATCHES_DIR = "patches"
PATCHES_LOG = os.path.join(PATCHES_DIR, "patches.json")
PATCHES_HISTORY = os.path.join(PATCHES_DIR, "history")


def _ensure_patches_dir():
    os.makedirs(PATCHES_DIR, exist_ok=True)
    os.makedirs(PATCHES_HISTORY, exist_ok=True)


def _read_patches_log():
    _ensure_patches_dir()
    if not os.path.exists(PATCHES_LOG):
        return {"patches": []}
    with open(PATCHES_LOG, "r", encoding="utf-8") as f:
        return json.load(f)


def _write_patches_log(data):
    _ensure_patches_dir()
    with open(PATCHES_LOG, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


router = APIRouter()


@router.get("/code/list-patches")
async def list_patches():
    return _read_patches_log()


@router.post("/code/apply")
async def apply_patch(payload: dict = Body(...)):
    """
    payload:
    {
      "id": "002-chat",
      "title": "Чат",
      "files": {
        "adaptive/adaptive.js": "...",
        "core/core.js": "...",
        "adaptive/adaptive.css": "..."
      }
    }
    """
    pid = payload.get("id")
    title = payload.get("title") or pid
    files = payload.get("files") or {}
    if not pid or not files:
        raise HTTPException(status_code=400, detail="id и files обязательны")

    _ensure_patches_dir()
    log_data = _read_patches_log()

    # 1. Сохраняем текущие версии файлов в history
    hist_dir = os.path.join(PATCHES_HISTORY, pid)
    os.makedirs(hist_dir, exist_ok=True)
    for path, content in files.items():
        try:
            with open(path, "r", encoding="utf-8") as f:
                old = f.read()
        except FileNotFoundError:
            old = ""
        safe = path.replace("/", "__")
        with open(os.path.join(hist_dir, safe), "w", encoding="utf-8") as f:
            f.write(old)

    # 2. Пишем новые версии
    for path, content in files.items():
        d = os.path.dirname(path)
        if d:
            os.makedirs(d, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

    # 3. Обновляем журнал
    entry = {
        "id": pid,
        "title": title,
        "date": datetime.utcnow().isoformat() + "Z",
        "files": list(files.keys()),
        "status": "applied",
    }
    log_data["patches"] = [p for p in log_data["patches"] if p.get("id") != pid]
    log_data["patches"].append(entry)
    _write_patches_log(log_data)

    return {"ok": True, "patch": entry}


@router.post("/code/rollback")
async def rollback_patch(payload: dict = Body(...)):
    """
    payload: { "id": "002-chat" }
    Возвращает файлы из patches/history/<id>/
    """
    pid = payload.get("id")
    if not pid:
        raise HTTPException(status_code=400, detail="id обязателен")

    hist_dir = os.path.join(PATCHES_HISTORY, pid)
    if not os.path.isdir(hist_dir):
        raise HTTPException(status_code=404, detail="история патча не найдена")

    log_data = _read_patches_log()
    entry = next((p for p in log_data["patches"] if p.get("id") == pid), None)
    if not entry:
        raise HTTPException(status_code=404, detail="патч не найден в журнале")

    for path in entry.get("files", []):
        safe = path.replace("/", "__")
        hist_path = os.path.join(hist_dir, safe)
        if os.path.exists(hist_path):
            with open(hist_path, "r", encoding="utf-8") as f:
                old = f.read()
            d = os.path.dirname(path)
            if d:
                os.makedirs(d, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(old)

    entry["status"] = "rolled-back"
    entry["rolled_at"] = datetime.utcnow().isoformat() + "Z"
    _write_patches_log(log_data)

    return {"ok": True, "patch": entry}


@router.get("/code/health")
async def code_health():
    """
    Метрика потолка: объём ядра, число патчей, число файлов.
    """
    _ensure_patches_dir()
    log_data = _read_patches_log()

    core_files = [
        "core/core.js", "core/core.css", "core/core-init.js",
        "core/prompts.py", "core/providers.py", "core/metrics.py", "core/chat.py",
        "adaptive/adaptive.js", "adaptive/adaptive.css",
        "adaptive/config.json", "adaptive/content.json",
        "adaptive/github_store.py", "adaptive/patches.py",
        "app.py", "index.html",
    ]
    core_size = 0
    for path in core_files:
        try:
            with open(path, "r", encoding="utf-8") as f:
                core_size += len(f.read())
        except FileNotFoundError:
            pass

    patches_count = len(log_data["patches"])
    files_count = len(set(f for p in log_data["patches"] for f in p.get("files", [])))

    ceiling_reached = core_size > 60000 or patches_count > 12

    return {
        "core_size": core_size,
        "patches_count": patches_count,
        "files_count": files_count,
        "ceiling_reached": ceiling_reached,
        "thresholds": {"core_size": 60000, "patches_count": 12},
    }