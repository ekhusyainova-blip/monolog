# app.py — тонкая точка входа Monolog.
# Отдаёт index.html и API.
# Структура A/B/C/D — в папках A_papka, B_papka, C_papka, D_papka.
# Пока подключена минимально.

import os
import json
import asyncio
import logging
from typing import List, Optional

import httpx
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

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
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

from fastapi.staticfiles import StaticFiles

app.mount("/core", StaticFiles(directory="core"), name="core")
app.mount("/adaptive", StaticFiles(directory="adaptive"), name="adaptive")

@app.get("/")
async def root():
    return FileResponse("index.html")


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "version": "structure-1.0",
        "branch": GITHUB_BRANCH,
        "github_ready": bool(GITHUB_TOKEN),
        "groq_keys": len(_DEV_KEYS_GROQ),
    }


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
        data = r.json()
        reply = data["choices"][0]["message"]["content"]
        return JSONResponse({"reply_text": reply})
    except Exception as e:
        return JSONResponse({"reply_text": f"Ошибка: {e}"})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=int(os.getenv("PORT", 8000)))