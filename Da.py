# Da.py — данные чата AI Monolog Chat
# Слой: данные. Логики нет. Только структуры и стартовое наполнение.

# ---------- ПРОВАЙДЕРЫ ----------
# priority: меньше = раньше. enabled: вкл/выкл целиком.
# base_url, models, model_default — для запросов.
# keys — список id ключей, привязанных к провайдеру.

PROVIDERS = [
    {
        "id": "groq",
        "name": "Groq",
        "base_url": "https://api.groq.com/openai/v1",
        "models": [
            "llama-3.3-70b-versatile",
            "llama-3.1-8b-instant",
            "mixtral-8x7b-32768",
        ],
        "model_default": "llama-3.3-70b-versatile",
        "priority": 1,
        "enabled": True,
        "keys": ["groq_1", "groq_2", "groq_3", "groq_4", "groq_5"],
    },
    {
        "id": "openrouter",
        "name": "OpenRouter",
        "base_url": "https://openrouter.ai/api/v1",
        "models": [
            "meta-llama/llama-3.3-70b-instruct:free",
            "google/gemma-2-9b-it:free",
        ],
        "model_default": "meta-llama/llama-3.3-70b-instruct:free",
        "priority": 2,
        "enabled": True,
        "keys": [],
    },
    {
        "id": "cerebras",
        "name": "Cerebras",
        "base_url": "https://api.cerebras.ai/v1",
        "models": ["llama3.3-70b", "llama3.1-8b"],
        "model_default": "llama3.3-70b",
        "priority": 3,
        "enabled": True,
        "keys": [],
    },
    {
        "id": "sambanova",
        "name": "SambaNova",
        "base_url": "https://api.sambanova.ai/v1",
        "models": ["Meta-Llama-3.3-70B-Instruct", "Meta-Llama-3.1-8B-Instruct"],
        "model_default": "Meta-Llama-3.3-70B-Instruct",
        "priority": 4,
        "enabled": True,
        "keys": [],
    },
    {
        "id": "custom",
        "name": "Свой",
        "base_url": "",
        "models": [],
        "model_default": "",
        "priority": 5,
        "enabled": False,
        "keys": [],
    },
]

# ---------- КЛЮЧИ ----------
# state: ok | cooldown | exhausted
# cooldown_until: unix-время, до которого ключ не трогаем
# value подтягивается из env по ENV_NAME, если пусто — из UI
# label: имя от пользователя (видно в интерфейсе)
# source: env | ui

KEYS = [
    {"id": "groq_1", "provider_id": "groq", "label": "Ключ 1", "env_name": "GROQ_KEY_1", "value": "", "state": "ok", "cooldown_until": 0, "last_used": 0, "source": "env"},
    {"id": "groq_2", "provider_id": "groq", "label": "Ключ 2", "env_name": "GROQ_KEY_2", "value": "", "state": "ok", "cooldown_until": 0, "last_used": 0, "source": "env"},
    {"id": "groq_3", "provider_id": "groq", "label": "Ключ 3", "env_name": "GROQ_KEY_3", "value": "", "state": "ok", "cooldown_until": 0, "last_used": 0, "source": "env"},
    {"id": "groq_4", "provider_id": "groq", "label": "Ключ 4", "env_name": "GROQ_KEY_4", "value": "", "state": "ok", "cooldown_until": 0, "last_used": 0, "source": "env"},
    {"id": "groq_5", "provider_id": "groq", "label": "Ключ 5", "env_name": "GROQ_KEY_5", "value": "", "state": "ok", "cooldown_until": 0, "last_used": 0, "source": "env"},
]

# ---------- ПРОМПТЫ ----------
# slot: layer_a | layer_b | layer_c | layer_d | layer_a_content
# active: выбран ли как рабочий в слоте
# slot_enabled: включён ли слот целиком
# source: local | repo
# file_path: путь в репо, если сохранён

PROMPTS = [
    {"id": "p_a_1", "slot": "layer_a", "name": "default", "text": "", "active": False, "slot_enabled": False, "source": "local", "file_path": "", "ts": 0},
    {"id": "p_a_2", "slot": "layer_a", "name": "strict", "text": "", "active": False, "slot_enabled": False, "source": "local", "file_path": "", "ts": 0},
    {"id": "p_b_1", "slot": "layer_b", "name": "default", "text": "", "active": False, "slot_enabled": False, "source": "local", "file_path": "", "ts": 0},
    {"id": "p_c_1", "slot": "layer_c", "name": "default", "text": "", "active": False, "slot_enabled": False, "source": "local", "file_path": "", "ts": 0},
    {"id": "p_d_1", "slot": "layer_d", "name": "default", "text": "", "active": False, "slot_enabled": False, "source": "local", "file_path": "", "ts": 0},
    {"id": "p_ac_1", "slot": "layer_a_content", "name": "base", "text": "", "active": False, "slot_enabled": False, "source": "local", "file_path": "", "ts": 0},
]

# Слоты промптов — фиксированный список (какие вообще бывают)
PROMPT_SLOTS = ["layer_a", "layer_b", "layer_c", "layer_d", "layer_a_content"]

# ---------- СООБЩЕНИЯ ----------
# role: user | assistant | system
# ts: unix-время создания (по нему чистка)
# provider_id, key_id — кто отвечал
# blocks: список блоков для рендера (текст / код / json)
#   блок: {"type": "text"|"code"|"json", "lang": "...", "content": "..."}

MESSAGES = []

# ---------- КОНТЕКСТЫ (сохранённые снимки) ----------
# messages — список сообщений на момент сохранения
# size — сколько байт занимает
# file_path — путь в репо

CONTEXTS = []

# ---------- НАСТРОЙКИ ----------
# provider_mode: auto | manual
# manual_provider_id: какой провайдер выбран вручную
# manual_key_id: какой ключ выбран вручную ("" = авто)
# autosave_enabled, autosave_every_n — автосейв контекста в репо
# autoclean_mb — лимит localStorage, автоочистка по размеру
# autoclean_days — автоочистка по возрасту сообщений
# stream — стримить ответ или нет

SETTINGS = {
    "provider_mode": "auto",
    "manual_provider_id": "",
    "manual_key_id": "",
    "autosave_enabled": True,
    "autosave_every_n": 20,
    "autoclean_mb": 4,
    "autoclean_days": 30,
    "stream": True,
}

# ---------- СОСТОЯНИЯ UI ----------
# тексты статусов, метки, цвета плашек — чтобы фронт не хардкодил

UI_STATES = {
    "key_states": {
        "ok": {"label": "работает", "color": "#2e7d32"},
        "cooldown": {"label": "остывает", "color": "#f9a825"},
        "exhausted": {"label": "исчерпан", "color": "#c62828"},
    },
    "providers_mode": {
        "auto": "Авто (по приоритету)",
        "manual": "Вручную",
    },
    "blocks": {
        "text": {"bg": "transparent", "copy": True},
        "code": {"bg": "#f4f4f4", "copy": True},
        "json": {"bg": "#f4f4f4", "copy": True},
    },
}

# ---------- СЛУЖБА БЕЗОПАСНОСТИ ----------
# один тип запроса, параметр режим
# notifications — полученные уведомления СБ

SB_REQUEST = {
    "type": "sb_query",
    "mode": "",          # режим задаётся из UI
    "message": "",       # без ограничения длины
}

SB_NOTIFICATIONS = []