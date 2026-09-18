# app.py — точка входа Monolog.
# Отдаёт index.html, /chat, /code/*, /state.
# Подключает структуру A/B/C/D.

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

# Подключение структуры A/B/C/D
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
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    return FileResponse("index.html")


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "version": "structure-1.2",
        "branch": GITHUB_BRANCH,
        "github_ready": bool(GITHUB_TOKEN),
        "groq_keys": len(_DEV_KEYS_GROQ),
    }


@app.get("/ui")
async def ui():
    """Тестовое подключение A/B/C/D."""
    data = {"input": {"hello": "world"}}
    a = A_AF.a_fragment(data)
    b = B_BF.b_fragment(data)
    c = C_CF.c_fragment(data)
    d = D_DF.d_fragment(data)
    return JSONResponse({"a": a, "b": b, "c": c, "d": d})


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
                headers={
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "openai/gpt-oss-20b",
                    "messages": [
                        {"role": "system", "content": "Ты