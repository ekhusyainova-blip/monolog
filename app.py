# app.py
# Monolog — stateless-прокси к Groq. Один этап, отключён thinking, отрезан reasoning-блок.

import os
import re
import json
import logging
import itertools
from typing import Optional, List, Dict, Any

import httpx
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("monolog")

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
MODEL = "qwen/qwen3.6-27b"
MAX_TOKENS = 2500
TIMEOUT = 60.0

_DEV_KEYS: List[str] = [k.strip() for k in os.getenv("GROQ_API_KEYS", "").split(",") if k.strip()]
_dev_key_cycle = itertools.cycle(_DEV_KEYS) if _DEV_KEYS else None
ALLOW_BYOK = os.getenv("ALLOW_BYOK", "true").lower() == "true"


def _load(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip()
    except FileNotFoundError:
        log.warning(f"Prompt file not found: {path}")
        return ""

LAYER_A = _load("prompts/layer_a.txt")
LAYER_B = _load("prompts/layer_b.txt")


def mask_key(key: str) -> str:
    if not key or len(key) < 12:
        return "***"
    return f"{key[:6]}...{key[-4:]}"


def next_dev_key() -> Optional[str]:
    if not _dev_key_cycle:
        return None
    return next(_dev_key_cycle)


def pick_key(request: Request):
    if ALLOW_BYOK:
        user_key = request.headers.get("X-Groq-Key", "").strip()
        if user_key.startswith("gsk_"):
            return user_key, "user"
    dev = next_dev_key()
    if dev:
        return dev, "developer"
    return None, "none"


BASE_METRICS = {
    "stability_index": 0.0,
    "indicator_status": "success",
    "cycles_completed": 0,
    "collisions_resolved": "0/0",
    "lots_balance": "+0.0",
    "patterns_applied": [],
    "cognitive_distortions": [],
    "autonomy_levels": [],
    "mind_scale": "micro",
    "human_contribution": 0.0,
    "value_choices": [],
    "consequences_tree": None,
    "dilemma_type": None,
    "impact_map": None,
    "reset_proposal": None,
    "artifact_status": None,
    "required_skills": [],
    "risk_intercept": None,
    "reasoning_trace": None,
    "breakthrough_marker": False,
    "cognitive_pulse": "slow",
    "protocol_integrity": True,
    "developer_mode": False,
}


def strip_thinking(text: str) -> str:
    """Убирает блоки рассуждений qwen3.6."""
    if not text:
        return text
    text = re.sub(r" thinking.*?", "", text, flags=re.DOTALL)
    text = re.sub(r"<reasoning>.*?</reasoning>", "", text, flags=re.DOTALL)
    return text.strip()


def extract_json(text: str) -> Optional[Dict[str, Any]]:
    if not text:
        return None
    text = strip_thinking(text)

    try:
        return json.loads(text)
    except Exception:
        pass

    m = re.search(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except Exception:
            pass

    start = text.find("{")
    while start != -1:
        depth = 0
        for i in range(start, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    chunk = text[start:i + 1]
                    try:
                        return json.loads(chunk)
                    except Exception:
                        break
        start = text.find("{", start + 1)
    return None


SYSTEM_PROMPT = (
    "Ты — когнитивный AI-партнёр Monolog. "
    "Отвечай ТОЛЬКО валидным JSON, без пояснений и размышлений. "
    "Ничего до { и ничего после }. "
    "Формат строго: {\"reply_text\": \"...\", \"metrics\": {...}}\n"
    "reply_text — Markdown-текст ответа на русском языке. БЕЗ ЭМОДЗИ. "
    "Используй Markdown: заголовки, списки, таблицы, код. "
    "metrics — строго по схеме ниже, все поля обязательны.\n\n"
    f"=== СЛОЙ A ===\n{LAYER_A}\n\n"
    f"=== СЛОЙ B ===\n{LAYER_B}\n\n"
    f"=== СХЕМА METRICS ===\n{json.dumps(BASE_METRICS, ensure_ascii=False)}"
)


async def groq_call(messages: List[Dict[str, str]], api_key: str) -> str:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": MODEL,
        "messages": messages,
        "max_tokens": MAX_TOKENS,
        "temperature": 0.6,
        "reasoning_effort": "none",
    }
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        r = await client.post(GROQ_URL, headers=headers, json=payload)

    remaining = r.headers.get("x-ratelimit-remaining-tokens", "?")
    log.info(f"Groq response: {r.status_code} | remaining tokens: {remaining}")

    if r.status_code == 429:
        retry_after = r.headers.get("retry-after", "неизвестно")
        raise HTTPException(
            status_code=429,
            detail=f"Лимит Groq исчерпан. Повторите через {retry_after} сек. Или введите свой ключ."
        )
    if r.status_code >= 400:
        log.error(f"Groq error {r.status_code}: {r.text[:300]}")
        raise HTTPException(status_code=r.status_code, detail="Ошибка Groq API")

    data = r.json()
    content = data["choices"][0]["message"]["content"]
    return strip_thinking(content)


app = FastAPI(title="Monolog MVP")
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
    return {"status": "ok", "dev_keys": len(_DEV_KEYS), "byok": ALLOW_BYOK}


@app.post("/chat")
async def chat(request: Request):
    body = await request.json()
    user_message = (body.get("message") or "").strip()
    history = body.get("history") or []
    attachments = body.get("attachments") or []

    if not user_message and not attachments:
        raise HTTPException(status_code=400, detail="Пустое сообщение")

    api_key, source = pick_key(request)
    if not api_key:
        raise HTTPException(status_code=503, detail="Нет доступных ключей. Введите свой ключ Groq.")

    log.info(f"Chat | key_source={source} | key={mask_key(api_key)} | len={len(user_message)} | files={len(attachments)}")

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for h in history[-4:]:
        if h.get("role") and h.get("content"):
            messages.append({"role": h["role"], "content": h["content"]})

    # Вложения добавляются как отдельный блок
    user_content = user_message or "Проанализируй вложения."
    if attachments:
        block = "\n\n=== ВЛОЖЕНИЯ ===\n"
        for a in attachments[:3]:
            block += f"\n[Файл: {a.get('name', 'без имени')}]\n{a.get('text', '')}\n"
        user_content = user_content + block

    messages.append({"role": "user", "content": user_content})

    raw = await groq_call(messages, api_key)

    parsed = extract_json(raw)
    if parsed and "reply_text" in parsed:
        metrics = {**BASE_METRICS, **(parsed.get("metrics") or {})}
        return JSONResponse({
            "reply_text": parsed["reply_text"],
            "metrics": metrics,
            "key_source": source,
        })

    log.warning(f"JSON parse failed. Raw (first 300): {raw[:300]}")
    cleaned = strip_thinking(raw)
    return JSONResponse({
        "reply_text": cleaned or "Не удалось получить корректный ответ. Попробуйте переформулировать.",
        "metrics": {**BASE_METRICS, "protocol_integrity": False, "indicator_status": "warning"},
        "key_source": source,
    })

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=int(os.getenv("PORT", 8000)))