# chat_c_chat.py
# Тема: chat
# Слой: C (решение)
# Что: формирование решения чата

# A · данные (внутри C)
# Какие данные для решения.
# Ключи, провайдеры, exhausted.

import os
import time

KEYS = {
    "groq": [k.strip() for k in os.getenv("GROQ_API_KEYS", "").split(",") if k.strip()],
    "cerebras": [os.getenv("CEREBRAS_API_KEY", "")],
    "sambanova": [os.getenv("SAMBANOVA_API_KEY", "")],
    "openrouter": [os.getenv("OPENROUTER_API_KEY", "")],
}

_rotation = {}
_exhausted = {}

# B · условие (внутри C)
# При каких условиях формируется решение.
# Есть ключи — решение формируется.

# C · решение
def pick_provider(preferred: str = None) -> str:
    """Выбрать провайдера."""
    if preferred and KEYS.get(preferred):
        return preferred
    for name in ["groq", "cerebras", "sambanova", "openrouter"]:
        if KEYS.get(name) and any(KEYS[name]):
            return name
    raise ValueError("Нет доступных провайдеров")

def pick_key(provider: str) -> str:
    """Выбрать ключ."""
    keys = KEYS.get(provider, [])
    keys = [k for k in keys if k]
    if not keys:
        raise ValueError(f"Нет ключей для {provider}")
    now = time.time()
    exhausted = _exhausted.get(provider, {})
    active = [k for k in keys if exhausted.get(k, 0) < now]
    if not active:
        _exhausted[provider] = {}
        active = keys
    idx = _rotation.get(provider, 0) % len(active)
    _rotation[provider] = idx + 1
    return active[idx]

def mark_exhausted(provider: str, key: str) -> None:
    _exhausted.setdefault(provider, {})[key] = time.time() + 65

# D · мета (внутри C)
# Куда выводится решение.
# В D (мета чата).