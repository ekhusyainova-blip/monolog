# Db.py — интерпретация чата AI Monolog Chat
# Слой: интерпретация. Читает Da, готовит данные для Dc.
# Сам не отправляет и не рендерит.

import time
from Da import PROVIDERS, KEYS, PROMPTS, SETTINGS, MESSAGES

# ---------- СОБЫТИЯ ----------
# Регистрация обработчиков. Логика ветвления — снаружи, данными.

HANDLERS = {}

def on(event, fn):
    HANDLERS.setdefault(event, []).append(fn)
    return fn

def emit(event, payload=None):
    for fn in HANDLERS.get(event, []):
        fn(payload or {})

# ---------- ВЫБОР ПРОВАЙДЕРА ----------
# auto: по priority, с учётом enabled и живых ключей
# manual: берём manual_provider_id из SETTINGS
# если у провайдера нет живых ключей — пропускаем (в auto)
# custom без base_url — пропускаем

def _keys_of(provider_id):
    return [k for k in KEYS if k["provider_id"] == provider_id]

def _key_alive(key):
    if key["state"] == "ok":
        return True
    if key["state"] == "cooldown":
        return time.time() >= key["cooldown_until"]
    return False

def _provider_alive(p):
    if not p["enabled"]:
        return False
    if not p["base_url"]:
        return False
    keys = _keys_of(p["id"])
    if not keys:
        return False
    return any(_key_alive(k) for k in keys)

def pick_provider():
    mode = SETTINGS.get("provider_mode", "auto")
    if mode == "manual":
        pid = SETTINGS.get("manual_provider_id", "")
        for p in PROVIDERS:
            if p["id"] == pid:
                return p if _provider_alive(p) else None
        return None
    alive = [p for p in PROVIDERS if _provider_alive(p)]
    alive.sort(key=lambda p: p["priority"])
    return alive[0] if alive else None

# ---------- ВЫБОР КЛЮЧА ----------
# Ротация: берём первый живой, у кого last_used самый старый.
# manual_key_id из SETTINGS — жёстко задан.
# После выбора обновляем last_used.

def pick_key(provider):
    manual = SETTINGS.get("manual_key_id", "")
    if manual:
        for k in KEYS:
            if k["id"] == manual and k["provider_id"] == provider["id"] and _key_alive(k):
                k["last_used"] = time.time()
                return k
        return None
    alive = [k for k in _keys_of(provider["id"]) if _key_alive(k)]
    if not alive:
        return None
    alive.sort(key=lambda k: k["last_used"])
    alive[0]["last_used"] = time.time()
    return alive[0]

# ---------- СБОРКА КОНТЕКСТА ----------
# Берём все сообщения подряд. Без обрезки — контекст отправляется полностью.
# Плюс системные промпты активных слотов.
# Промпты идут перед сообщениями, порядок: a, a_content, b, c, d.

PROMPT_ORDER = ["layer_a", "layer_a_content", "layer_b", "layer_c", "layer_d"]

def active_prompt(slot):
    for p in PROMPTS:
        if p["slot"] == slot and p["active"] and p["slot_enabled"] and p["text"].strip():
            return p
    return None

def build_system():
    parts = []
    for slot in PROMPT_ORDER:
        p = active_prompt(slot)
        if p:
            parts.append(p["text"].strip())
    return "\n\n".join(parts)

def build_messages():
    msgs = []
    system = build_system()
    if system:
        msgs.append({"role": "system", "content": system})
    for m in MESSAGES:
        msgs.append({"role": m["role"], "content": m["content"]})
    return msgs

# ---------- СОБЫТИЯ ЖИЗНЕННОГО ЦИКЛА ----------

@on("user_message")
def handle_user_message(payload):
    text = payload.get("text", "")
    if not text:
        emit("error", {"where": "db", "msg": "пустое сообщение"})
        return
    provider = pick_provider()
    if not provider:
        emit("error", {"where": "db", "msg": "нет живых провайдеров"})
        return
    key = pick_key(provider)
    if not key:
        emit("error", {"where": "db", "msg": "нет живых ключей"})
        return
    emit("request_ready", {
        "provider": provider,
        "key_id": key["id"],
        "model": provider["model_default"],
        "messages": build_messages(),
        "stream": SETTINGS.get("stream", True),
        "text": text,
    })

# ---------- ОБРАБОТКА ОТКАЗОВ ----------
# Пришёл 429/ошибка от провайдера — помечаем ключ и пробуем снова.

@on("provider_fail")
def handle_provider_fail(payload):
    key_id = payload.get("key_id", "")
    status = payload.get("status", 0)
    for k in KEYS:
        if k["id"] == key_id:
            if status == 429:
                k["state"] = "cooldown"
                k["cooldown_until"] = time.time() + 60
            elif status in (401, 403):
                k["state"] = "exhausted"
            else:
                k["state"] = "cooldown"
                k["cooldown_until"] = time.time() + 15
    emit("retry", {"reason": "fail", "status": status})

@on("provider_ok")
def handle_provider_ok(payload):
    key_id = payload.get("key_id", "")
    for k in KEYS:
        if k["id"] == key_id:
            k["state"] = "ok"
            k["cooldown_until"] = 0