import os
import json
import re
import time
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from groq import Groq
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

GROQ_API_KEYS_RAW = os.environ.get("GROQ_API_KEYS", "").strip()
if not GROQ_API_KEYS_RAW:
    raise ValueError("КРИТИЧЕСКАЯ ОШИБКА: Переменная GROQ_API_KEYS не задана!")

GROQ_API_KEYS = [k.strip() for k in GROQ_API_KEYS_RAW.split(",") if k.strip()]
if not GROQ_API_KEYS:
    raise ValueError("КРИТИЧЕСКАЯ ОШИБКА: Не найдено ни одного GROQ_API_KEY!")

logger.info(f"Загружено {len(GROQ_API_KEYS)} API ключей Groq")

rotation_state = {
    "current_index": 0,
    "switches_count": 0,
    "keys_stats": [{"key": k[:4] + "***" + k[-4:] if len(k) > 8 else "***", "used": 0, "errors": 0} for k in GROQ_API_KEYS]
}

def get_current_client() -> Groq:
    return Groq(api_key=GROQ_API_KEYS[rotation_state["current_index"]])

def switch_to_next_key():
    rotation_state["current_index"] = (rotation_state["current_index"] + 1) % len(GROQ_API_KEYS)
    rotation_state["switches_count"] += 1
    logger.info(f"Переключение на ключ #{rotation_state['current_index']}")

def call_groq_with_rotation(messages, temperature=0.7, max_tokens=4000, timeout=60):
    attempts = len(GROQ_API_KEYS)
    last_error = None
    for attempt in range(attempts):
        current_idx = rotation_state["current_index"]
        client = get_current_client()
        try:
            logger.info(f"Попытка #{attempt + 1}: ключ #{current_idx}")
            completion = client.chat.completions.create(
                model="qwen/qwen3.6-27b",
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=timeout
            )
            rotation_state["keys_stats"][current_idx]["used"] += 1
            logger.info(f"Успех на ключе #{current_idx}")
            return completion.choices[0].message.content
        except Exception as e:
            error_str = str(e)
            rotation_state["keys_stats"][current_idx]["errors"] += 1
            last_error = e
            if "rate_limit_exceeded" in error_str or "429" in error_str or "Request too large" in error_str:
                logger.warning(f"Rate limit на ключе #{current_idx}. Переключаюсь...")
                switch_to_next_key()
                continue
            else:
                logger.error(f"Ошибка Groq: {e}")
                raise e
    raise Exception(f"Все ключи исчерпали лимит. Ошибка: {last_error}")
