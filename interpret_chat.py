# interpret_chat.py

import os

STARTER_PATH = os.path.join(os.path.dirname(__file__), "starter.md")

# читаем один раз при импорте
with open(STARTER_PATH, "r", encoding="utf-8") as f:
    STARTER = f.read()


def build_messages(reflection: str, query: str, first_time: bool) -> list:
    """
    Собирает messages для Groq.

    reflection — сводка отражения из IndexedDB (фронт присылает)
    query — текущий запрос пользователя
    first_time — True при открытии чата, False дальше
    """
    messages = []

    if first_time:
        messages.append({
            "role": "system",
            "content": STARTER
        })
        if reflection:
            messages.append({
                "role": "system",
                "content": reflection
            })

    messages.append({
        "role": "user",
        "content": query
    })

    return messages