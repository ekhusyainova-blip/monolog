# core/prompts.py — загрузка промптов ядра.
# Три файла: layer_a (смысл), layer_b (мета), layer_a_content (форма ответа).
# Файлы читаются один раз при импорте.

import logging

log = logging.getLogger("monolog")


def _load(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip()
    except FileNotFoundError:
        log.warning(f"Prompt file not found: {path}")
        return ""


LAYER_A = _load("prompts/layer_a.txt")
LAYER_B = _load("prompts/layer_b.txt")
LAYER_A_CONTENT = _load("prompts/layer_a_content_prompt")