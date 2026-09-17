# core_backend/providers.py
# Работа с LLM-провайдерами: выбор модели, вызов, обработка ответа.
# Без роутера.

import re
import json
from typing import Optional, Dict, Any

import httpx
from fastapi import HTTPException

from core_backend.config import (
    PROVIDERS,
    MAX_TOKENS,
    TIMEOUT,
    safe_log,
    next_dev_key,
)


def strip_thinking(text: str) -> str:
    """Убирает reasoning-блоки из ответа модели."""
    if not text:
        return text
    text = re.sub(r" thinking.*?", "", text, flags=re.DOTALL)
    text = re.sub(r"<reasoning>.*?</reasoning>", "", text, flags=re.DOTALL)
    return text.strip()


def extract_json(text: str) -> Optional[Dict[str, Any]]:
    """Пытается вытащить JSON-объект из ответа модели."""
    if not text:
        return None
    text = text.replace("\ufeff", "").replace("\u200b", "").replace("\u200c", "").replace("\u200d", "")
    text = strip_thinking(text)
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```\s*$", "", text)
    start = text.find("{")
    if start == -1:
        return None
    try:
        return json.loads(text[start:])
    except Exception:
        pass
    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(text)):
        ch = text[i]
        if escape:
            escape = False
            continue
        if ch == "\\":
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                chunk = text[start:i + 1]
                try:
                    return json.loads(chunk)
                except Exception:
                    fixed = re.sub(r"(?<!\\)\n", "\\\\n", chunk)
                    try:
                        return json.loads(fixed)
                    except Exception:
                        return None
    return None


def _pick_model_tier(user_message, carried_metrics, models):
    """Выбирает уровень модели: light / medium / heavy."""
    text = (user_message or "").lower()
    heavy_keywords = [
        "статья", "лонгрид", "пост", "напиши",
        "проанализируй", "анализ", "план", "стратег",
        "архитектур", "спроектируй", "разработай",
        "документ", "тз", "отчёт", "отчет",
    ]
    if any(kw in text for kw in heavy_keywords):
        return models.get("heavy") or models.get("medium") or models.get("light")
    if len(user_message or "") > 200:
        return models.get("medium") or models.get("light")
    if carried_metrics:
        passport = carried_metrics.get("passport") or {}
        if passport.get("level") in ("strategic", "systemic"):
            return models.get("medium") or models.get("light")
    return models.get("light") or models.get("medium")


def pick_provider_and_model(body, user_message, carried_metrics=None):
    """Определяет провайдера, URL, модель и ключ. Возвращает кортеж."""
    provider = (body.get("provider") or "groq").strip().lower()
    if provider not in PROVIDERS:
        provider = "groq"
    user_key = (body.get("api_key") or "").strip()
    if user_key and len(user_key) > 20:
        cfg = PROVIDERS[provider]
        model = _pick_model_tier(user_message, carried_metrics, cfg["models"])
        return provider, cfg["base_url"], model, user_key, "user"
    dev_key = next_dev_key()
    if dev_key:
        cfg = PROVIDERS["groq"]
        model = _pick_model_tier(user_message, carried_metrics, cfg["models"])
        return "groq", cfg["base_url"], model, dev_key, "developer"
    return None, None, None, None, "none"


async def call_provider(messages, api_key, base_url, model, provider, max_tokens=MAX_TOKENS):
    """Универсальный вызов LLM-провайдера."""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    if provider == "openrouter":
        headers["HTTP-Referer"] = "https://monolog.onrender.com"
        headers["X-Title"] = "AI Monolog"
    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": 0.6,
    }
    cfg = PROVIDERS.get(provider, {})
    if cfg.get("reasoning_effort"):
        if model.startswith("openai/gpt-oss") or model.startswith("gpt-oss"):
            payload["reasoning_effort"] = "low"
        elif model.startswith("qwen"):
            payload["reasoning_effort"] = "none"

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        r = await client.post(base_url, headers=headers, json=payload)
        remaining = r.headers.get("x-ratelimit-remaining-tokens", "?")
        safe_log(f"Provider [{provider}/{model}] status={r.status_code} remaining={remaining}")
        if r.status_code == 429:
            retry_after = r.headers.get("retry-after")
            detail = (f"Лимит ключа исчерпан. Повторите через {retry_after} сек."
                      if retry_after else
                      "Лимит ключа исчерпан. Он обновится автоматически. Или введите свой ключ в настройках → Ключ API.")
            raise HTTPException(status_code=429, detail=detail)
        if r.status_code == 402:
            raise HTTPException(status_code=402, detail="На провайдере закончились кредиты.")
        if r.status_code in (401, 403):
            raise HTTPException(status_code=403, detail="Ключ не принят провайдером.")
        if r.status_code == 413:
            raise HTTPException(status_code=413, detail="Запрос слишком длинный.")
        if r.status_code >= 500:
            safe_log(f"Provider error {r.status_code}")
            name = PROVIDERS.get(provider, {}).get("name", provider)
            raise HTTPException(status_code=502, detail=f"{name} недоступен. Попробуйте позже.")
        if r.status_code >= 400:
            safe_log(f"Provider error {r.status_code}")
            name = PROVIDERS.get(provider, {}).get("name", provider)
            raise HTTPException(status_code=r.status_code, detail=f"Ошибка {name} API.")
        data = r.json()
        return strip_thinking(data["choices"][0]["message"]["content"])