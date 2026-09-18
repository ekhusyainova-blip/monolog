# A_papka/B_file.py
# Запросы — коннектор.
# Связывает данные с интерпретацией, решением, результатом.
# Вывод: в C файл A папки.
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

# [D] d_fragment — запрос результата
def d_fragment(data):
    return {"ask_result": data.get("facts", {})}

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

# [D-fix] d_fragment_fix — фикс запроса результата
def d_fragment_fix():
    return {"ask_result": {}}

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