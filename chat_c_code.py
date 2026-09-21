# chat_c_code.py
# Тема: code
# Слой: C (решение)
# Что: какую часть кода использовать

def pick_module(theme: str) -> str:
    if theme in MODULES:
        return theme
    return "chat"