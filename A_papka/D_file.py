# A_papka/D_file.py
# Запросы — вывод.
# Формирует финальный запрос: в файл, пользователю или мне.
# Только события. Данные приходят снаружи.

# --- фрагменты A/B/C/D (обычные) ---

# [A] a_fragment — запрос фактов
def a_fragment(data):
    return {"facts": data.get("facts", {})}

# [B] b_fragment — запрос интерпретации
def b_fragment(data):
    return {"ask_interpretation": data.get("facts", {})}

# [C] c_fragment — запрос решения
def c_fragment(data):
    return {"ask_decision": data.get("facts", {})}

# [D] d_fragment — запрос вывода
def d_fragment(data):
    return {
        "ask_result": data.get("facts", {}),
        "output": data.get("output", "me"),
    }

# --- фрагменты A/B/C/D (фикс) ---

# [A-fix] a_fragment_fix — фикс фактов
def a_fragment_fix():
    return {"facts": {}}

# [B-fix] b_fragment_fix — фикс запроса интерпретации
def b_fragment_fix():
    return {"ask_interpretation": {}}

# [C-fix] c_fragment_fix — фикс запроса решения
def c_fragment_fix():
    return {"ask_decision": {}}

# [D-fix] d_fragment_fix — фикс запроса вывода
def d_fragment_fix():
    return {"ask_result": {}, "output": "me"}

# --- служебные ---

# [off] off — список элементов для скрытия
def off(elements):
    return {"hidden": list(elements)}

# [filter] filter — приоритет искажённых над чистыми
def filter(clean, distorted):
    return {"used": distorted if distorted else clean,
            "distorted": bool(distorted)}

# [stub] stub — активные и отключённые фрагменты
def stub(active, disabled):
    return {"active": list(active), "disabled": list(disabled)}