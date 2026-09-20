# Dd.py — мета чата AI Monolog Chat
# Слой: мета. Решает, что выводить и куда. Сам не выводит.
# Слушает события, формирует пакеты для фронта.

from Db import on, emit
from Da import SETTINGS, UI_STATES, PROVIDERS, KEYS, PROMPTS, MESSAGES, CONTEXTS

# ---------- СОСТОЯНИЕ ИНТЕРФЕЙСА ----------
# Что открыто, что в фокусе, какой режим отображения.
# Фронт читает и меняет через events.

UI = {
    "view": "chat",                 # chat | settings | sb | status | contexts
    "panel": "",                    # открытая секция настроек
    "focus_msg": "",                # id сообщения в фокусе
    "show_repo": False,             # показывать что в репо
    "streaming": False,             # идёт ли стрим сейчас
    "buffer": "",                   # текущий накапливаемый ответ
}

# ---------- КАНАЛЫ ВЫВОДА ----------
# Каждое событие раскладывается в один из каналов.
# Канал — это то, что фронт умеет рендерить.

CHANNELS = {
    "message": [],      # готовые сообщения
    "chunk": [],        # куски стрима
    "status": [],       # статусы (провайдер, ключ, стрим)
    "error": [],        # ошибки
    "notice": [],       # уведомления СБ и прочие
    "ui": [],           # изменения интерфейса
}

def _push(channel, payload):
    CHANNELS[channel].append(payload)
    emit("ui_update", {"channel": channel, "payload": payload})

# ---------- СТРИМ ----------
# Пришёл chunk — копим в буфер, отдаём в канал chunk.
# Стрим закончился — отдаём финальное сообщение.

@on("stream_start")
def on_stream_start(payload):
    UI["streaming"] = True
    UI["buffer"] = ""
    _push("status", {"kind": "stream", "state": "start", **payload})

@on("chunk")
def on_chunk(payload):
    UI["buffer"] += payload.get("text", "")
    _push("chunk", {"text": payload.get("text", "")})

@on("stream_end")
def on_stream_end(payload):
    raw = UI["buffer"]
    UI["streaming"] = False
    _push("status", {"kind": "stream", "state": "end"})
    emit("save_assistant", {
        "text": raw,
        "id": payload.get("id", ""),
        "ts": payload.get("ts", 0),
        "provider_id": payload.get("provider_id", ""),
        "key_id": payload.get("key_id", ""),
    })

# ---------- СОХРАНЕНИЕ И ВЫВОД СООБЩЕНИЙ ----------

@on("message_saved")
def on_message_saved(msg):
    _push("message", msg)

# ---------- ОШИБКИ И УВЕДОМЛЕНИЯ ----------

@on("error")
def on_error(payload):
    _push("error", payload)

@on("notice")
def on_notice(payload):
    _push("notice", payload)

# ---------- РЕТРАЙ ----------
# Db просит повторить — ищем следующий живой ключ и запускаем снова.

@on("retry")
def on_retry(payload):
    _push("status", {"kind": "retry", **payload})
    emit("user_message", {"text": payload.get("text", "")})

# ---------- СНАПШОТ ДЛЯ ФРОНТА ----------
# Фронт при загрузке просит всё состояние разом.

@on("ui_snapshot")
def on_snapshot(payload=None):
    snapshot = {
        "ui": dict(UI),
        "providers": PROVIDERS,
        "keys": [{k: v for k, v in key.items() if k != "value"} for key in KEYS],
        "prompts": PROMPTS,
        "slots": UI_STATES,
        "settings": SETTINGS,
        "contexts": CONTEXTS,
        "messages_count": len(MESSAGES),
    }
    _push("ui", {"kind": "snapshot", "data": snapshot})

# ---------- ПЕРЕКЛЮЧЕНИЕ ВИДА ----------

@on("set_view")
def on_set_view(payload):
    UI["view"] = payload.get("view", "chat")
    _push("ui", {"kind": "view", "value": UI["view"]})

@on("set_panel")
def on_set_panel(payload):
    UI["panel"] = payload.get("panel", "")
    _push("ui", {"kind": "panel", "value": UI["panel"]})

@on("toggle_repo")
def on_toggle_repo(payload=None):
    UI["show_repo"] = not UI["show_repo"]
    _push("ui", {"kind": "show_repo", "value": UI["show_repo"]})