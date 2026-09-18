# D_papka/A_file.py
# Мета — данные.
# Принимает мета-данные: переменные, значения, вход.
# Вывод: в A файл A папки.
# Только события. Данные приходят снаружи.

# --- фрагменты A/B/C/D (обычные) ---

# [A] a_fragment — переменные и значения
def a_fragment(data):
    return {"variables": data.get("variables", {})}

# [B] b_fragment — получает условия и события
def b_fragment(data):
    return {
        "conditions": data.get("conditions", []),
        "events": data.get("events", []),
    }

# [C] c_fragment — получает решение и действует
def c_fragment(data):
    return {"decision": data.get("decision", {}), "acted": True}

# [D] d_fragment — получает и выводит результат
def d_fragment(data):
    return {"result": data.get("result", {})}

# --- фрагменты A/B/C/D (фикс) ---

# [A-fix] a_fragment_fix — фикс переменных
def a_fragment_fix():
    return {"variables": {}}

# [B-fix] b_fragment_fix — фикс условий и событий
def b_fragment_fix():
    return {"conditions": [], "events": []}

# [C-fix] c_fragment_fix — фикс решения
def c_fragment_fix():
    return {"decision": {}, "acted": True}

# [D-fix] d_fragment_fix — фикс результата
def d_fragment_fix():
    return {"result": {}}

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