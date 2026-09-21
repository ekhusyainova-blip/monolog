# chat_b_chat.py
# Тема: chat
# Слой: B (условие)
# Что: условие применения чата

# A · данные (внутри B)
# Какие данные для условия.
# События чата.

# B · условие
def when_chat_active(event: dict) -> bool:
    """При каких условиях чат активен."""
    return bool(event.get("text", "").strip())

# C · решение (внутри B)
def build_request(event: dict, context: list) -> dict:
    """Собрать запрос."""
    system = "\n".join([
        "Ты — Monolog. Факты.",
        "Ты — Monolog. Интерпретации.",
        "Ты — Monolog. Решения.",
        "Ты — Monolog. Мета.",
    ])
    messages = [{"role": "system", "content": system}]
    for msg in context[-20:]:
        if isinstance(msg, dict) and "role" in msg and "content" in msg:
            messages.append(msg)
    messages.append({"role": "user", "content": event["text"]})
    return {
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": 2048,
    }

# D · мета (внутри B)
# Куда выводится условие.
# В C (решение чата).