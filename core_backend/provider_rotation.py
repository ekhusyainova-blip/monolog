# core_backend/provider_rotation.py
# Ротация между провайдерами: если один упал — пробуем следующий.
# Используется в chat.py для устойчивости вызовов.

from typing import Optional, List, Dict, Any

from fastapi import HTTPException

from core_backend.config import (
    PROVIDERS,
    next_provider_key,
    safe_log,
)
from core_backend.providers import call_provider


# Порядок ротации: сначала groq, потом остальные
_ROTATION_ORDER: List[str] = ["groq", "openrouter", "cerebras", "sambanova"]


async def call_with_fallback(
    messages: List[Dict[str, Any]],
    user_api_key: Optional[str] = None,
    user_provider: Optional[str] = None,
    user_model: Optional[str] = None,
    max_tokens: int = 3500,
) -> Dict[str, Any]:
    """
    Вызывает провайдера с автоматическим fallback.

    Если user_api_key задан — используется он, без ротации.
    Иначе — берём ключи из config и пробуем по очереди.

    Возвращает:
        {"text": str, "provider": str, "model": str, "source": str}
    """

    # --- Если пользователь дал свой ключ — используем его без ротации ---
    if user_api_key and len(user_api_key) > 20:
        provider = user_provider or "groq"
        if provider not in PROVIDERS:
            provider = "groq"
        cfg = PROVIDERS[provider]
        model = user_model or cfg["models"].get("light") or cfg["models"].get("medium")
        text = await call_provider(
            messages, user_api_key, cfg["base_url"], model, provider, max_tokens=max_tokens,
        )
        return {
            "text": text,
            "provider": provider,
            "model": model,
            "source": "user",
        }

    # --- Иначе — ротация по провайдерам ---
    last_error: Optional[Exception] = None
    tried: List[str] = []

    for provider_id in _ROTATION_ORDER:
        if provider_id in tried:
            continue
        tried.append(provider_id)

        key_info = next_provider_key()
        if not key_info:
            continue

        provider, api_key = key_info
        cfg = PROVIDERS.get(provider)
        if not cfg:
            continue

        # Модель для провайдера
        if provider == "groq":
            model = cfg["models"].get("light") or cfg["models"].get("medium")
        else:
            model = cfg["models"].get("light") or cfg["models"].get("medium") or cfg["models"].get("heavy")

        try:
            text = await call_provider(
                messages, api_key, cfg["base_url"], model, provider, max_tokens=max_tokens,
            )
            safe_log(f"Fallback успех: {provider}/{model}")
            return {
                "text": text,
                "provider": provider,
                "model": model,
                "source": "developer",
            }
        except HTTPException as e:
            safe_log(f"Fallback провайдер {provider} упал: {e.status_code} {e.detail}")
            last_error = e
            continue
        except Exception as e:
            safe_log(f"Fallback провайдер {provider} упал: {e}")
            last_error = e
            continue

    # --- Все провайдеры упали ---
    if isinstance(last_error, HTTPException):
        raise last_error
    raise HTTPException(
        status_code=503,
        detail="Все провайдеры недоступны. Попробуйте позже.",
    )