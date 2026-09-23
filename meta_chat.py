# meta_chat.py

import re
import json


MARKER_RE = re.compile(r"\[(sphere|ui):\s*(\{.*?\})\]")


def parse(raw: str) -> dict:
    """
    Возвращает:
      text — чистый текст без маркеров
      markers — список маркеров
    """
    markers = []

    for match in MARKER_RE.finditer(raw):
        kind = match.group(1)
        try:
            payload = json.loads(match.group(2))
        except json.JSONDecodeError:
            continue
        markers.append({"kind": kind, "payload": payload})

    text = MARKER_RE.sub("", raw).strip()

    return {
        "text": text,
        "markers": markers
    }