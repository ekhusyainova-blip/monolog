# core_backend/config.py
# Конфигурация Monolog: переменные окружения, провайдеры, константы.
# Импортируется всеми остальными модулями backend.

import os
import re
import logging
import itertools
from typing import Optional, List

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("monolog")

SECRET_PATTERN = re.compile(r"(sk_[A-Za-z0-9_\-]{8,}|gsk_[A-Za-z0-9_\-]{8,}|Bearer\s+[A-Za-z0-9_\-\.]{10,})")


def safe_log(msg: str):
    """Логирует сообщение, скрывая секреты."""
    log.info(SECRET_PATTERN.sub("[SECRET]", str(msg)))


# --- Провайдеры LLM ---
PROVIDERS = {
    "groq": {
        "name": "Groq",
        "base_url": "https://api.groq.com/openai/v1/chat/completions",
        "models": {
            "light": "openai/gpt-oss-20b",
            "medium": "openai/gpt-oss-120b",
            "heavy": "qwen/qwen3.6-27b",
        },
        "all_models": [
            "openai/gpt-oss-20b",
            "openai/gpt-oss-120b",
            "qwen/qwen3.6-27b",
            "llama-3.3-70b-versatile",
            "llama-3.1-8b-instant",
        ],
        "reasoning_effort": True,
    },
    "openrouter": {
        "name": "OpenRouter",
        "base_url": "https://openrouter.ai/api/v1/chat/completions",
        "models": {
            "light": "openai/gpt-oss-20b:free",
            "medium": "openai/gpt-oss-120b:free",
            "heavy": "qwen/qwen-coder:free",
        },
        "all_models": [
            "openai/gpt-oss-20b:free",
            "openai/gpt-oss-120b:free",
            "qwen/qwen-coder:free",
            "meta-llama/llama-3.3-70b-instruct:free",
            "google/gemma-2-9b-it:free",
        ],
        "reasoning_effort": False,
    },
    "cerebras": {
        "name": "Cerebras",
        "base_url": "https://api.cerebras.ai/v1/chat/completions",
        "models": {
            "light": "gpt-oss-20b",
            "medium": "gpt-oss-120b",
            "heavy": "gpt-oss-120b",
        },
        "all_models": ["gpt-oss-20b", "gpt-oss-120b", "llama3.1-8b", "llama3.1-70b"],
        "reasoning_effort": True,
    },
    "sambanova": {
        "name": "SambaNova",
        "base_url": "https://api.sambanova.ai/v1/chat/completions",
        "models": {
            "light": "Meta-Llama-3.3-70B-Instruct",
            "medium": "Meta-Llama-3.3-70B-Instruct",
            "heavy": "DeepSeek-V3.1",
        },
        "all_models": [
            "Meta-Llama-3.3-70B-Instruct",
            "Meta-Llama-3.1-8B-Instruct",
            "DeepSeek-V3.1",
        ],
        "reasoning_effort": False,
    },
}

# --- Лимиты ---
MAX_TOKENS = 3500
META_MAX_TOKENS = 800
TIMEOUT = 120.0

MAX_MESSAGE_LEN = 8000
SOFT_MESSAGE_LEN = 4000
MAX_ATTACH_LEN = 3000
MAX_ATTACHMENTS = 3
MAX_BODY_BYTES = 200_000

# --- Ключи разработчика ---
_DEV_KEYS_GROQ: List[str] = [
    k.strip() for k in os.getenv("GROQ_API_KEYS", "").split(",") if k.strip()
]
_dev_key_cycle = itertools.cycle(_DEV_KEYS_GROQ) if _DEV_KEYS_GROQ else None


def next_dev_key() -> Optional[str]:
    """Возвращает следующий ключ Groq по кругу."""
    if not _dev_key_cycle:
        return None
    return next(_dev_key_cycle)


# --- Флаги и секреты ---
ALLOW_BYOK = os.getenv("ALLOW_BYOK", "true").lower() == "true"
MANAGEMENT_KEY = os.getenv("MANAGEMENT_KEY", "").strip()
AUTHOR_SECRET = os.getenv("AUTHOR_SECRET", "").strip()

CORS_ORIGINS_ENV = os.getenv("CORS_ORIGINS", "*").strip()
CORS_ORIGINS = [o.strip() for o in CORS_ORIGINS_ENV.split(",") if o.strip()] or ["*"]

# --- GitHub ---
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "").strip()
GITHUB_REPO = os.getenv("GITHUB_REPO", "ekhusyainova-blip/monolog").strip()
GITHUB_BRANCH = os.getenv("GITHUB_BRANCH", "main").strip()
CODE_BRANCH = os.getenv("CODE_BRANCH", "dev").strip()

GITHUB_API = "https://api.github.com"

# --- Пути к данным ---
BLOG_PATH = "blog/posts.json"
RELEASES_PATH = "releases.json"
PUBLIC_TEMPLATES_PATH = "public/templates.json"
PUBLIC_LOTS_PATH = "public/lots.json"
PUBLIC_REVIEWS_PATH = "public/reviews.json"
PUBLIC_REPUTATION_PATH = "public/reputation.json"


def _load(path: str) -> str:
    """Читает промпт из файла. Возвращает пустую строку, если файла нет."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip()
    except FileNotFoundError:
        log.warning(f"Prompt file not found: {path}")
        return ""


# --- Промпты (пустые — модель достраивает из ядра) ---
LAYER_A = _load("prompts/layer_a.txt")
LAYER_B = _load("prompts/layer_b.txt")
LAYER_A_CONTENT = _load("prompts/layer_a_content_prompt")