# chat_d_chat.py
# Тема: chat
# Слой: D (мета)
# Что: мета, маршрутизация чата

# A · данные (внутри D)
# Какие данные для мета.
# Результат C.

# B · условие (внутри D)
# При каких условиях мета срабатывает.
# После C.

# C · решение (внутри D)
# Решение: что делать с результатом.

# D · мета
def build_response(answer: str, provider: str, elapsed: float) -> dict:
    return {
        "ok": True,
        "data": {
            "answer": answer,
            "provider": provider,
            "elapsed": round(elapsed, 3),
        },
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }

def build_error(code: int, cls: str, msg: str) -> dict:
    return {
        "ok": False,
        "error": {"code": code, "class": cls, "message": msg},
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }

def route(result: dict, event: dict) -> dict:
    """Куда отдать результат."""
    if not result.get("ok"):
        return {"target": "error", "payload": result}
    return {"target": "user", "payload": result}

# Куда выводится мета.
# В A (обратно).