# core_backend/metrics.py
# Метрики Monolog: базовый набор, слияние, компактное состояние.

from typing import Optional, Dict, Any


BASE_METRICS = {
    "stability_index": 0.0,
    "indicator_status": "success",
    "cycles_completed": 0,
    "lots_balance": "+0.0",
    "index_delta": None,
    "mind_scale": "micro",
    "human_contribution": 0.0,
    "cognitive_pulse": "stable",
    "mode_suggested": "analyst",
    "layer_marker": None,
    "ai_note": None,
    "learning_template": None,
    "reset_proposal": None,
    "reminder": None,
    "value_choices": [],
    "risk_intercept": None,
    "social_adaptation": {"active": False, "reason": None, "level": "inactive"},
    "dominant_trait": {
        "detected": False,
        "influence": None,
        "risk": None,
        "stability_delta": 0.0,
        "hint": None,
        "steps": [],
    },
    "passport": {
        "level": "micro",
        "title": None,
        "goal": None,
        "result": None,
        "mission": None,
        "values": [],
        "constraints": [],
        "stakeholders": [],
        "risks": [],
        "metrics": [],
        "completion": 0,
    },
    "profile": {
        "values": {},
        "patterns": [],
        "distortions": [],
        "insights": [],
        "somatic": {
            "energy": 0.5,
            "tension": 0.3,
            "focus": 0.5,
            "mood": None,
            "note": None,
        },
        "skills": [],
    },
    "dimension": None,
    "priority_drift": None,
    "mood_board": None,
    "ideas": [],
    "artifacts": [],
    "protocol_integrity": True,
    "management_mode": False,
    "public_index": {
        "given": 0,
        "taken": 0,
        "help_score": 0,
        "reputation": 0,
    },
}


def compact_carried(carried: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Сжимает состояние до ключевых полей — для передачи в LLM."""
    if not carried:
        return {}
    out = {}
    p = carried.get("passport") or {}
    if p:
        out["passport"] = {
            "level": p.get("level"),
            "title": p.get("title"),
            "goal": p.get("goal"),
        }
    pr = carried.get("profile") or {}
    if pr:
        out["profile"] = {
            "values": pr.get("values") or {},
            "patterns": (pr.get("patterns") or [])[:5],
        }
    arts = carried.get("artifacts") or []
    if arts:
        compacted = []
        for a in arts[-3:]:
            if not isinstance(a, dict):
                continue
            item = {
                "id": a.get("id"),
                "name": a.get("name"),
                "type": a.get("type"),
                "version": a.get("version"),
                "stage": a.get("stage"),
            }
            content = a.get("content") or ""
            if content and len(content) < 6000:
                item["content"] = content
            compacted.append(item)
        out["artifacts"] = compacted
    return out


def merge_metrics(incoming: Optional[Dict[str, Any]], carried: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Сливает входящие метрики с уже накопленными."""
    carried = carried or {}
    result = {**BASE_METRICS, **carried}
    skip_keys = (
        "passport", "profile", "reminder", "artifacts",
        "social_adaptation", "dominant_trait", "ideas",
        "dimension", "priority_drift", "mood_board",
    )
    for k, v in (incoming or {}).items():
        if k in skip_keys:
            continue
        if v is not None:
            result[k] = v

    inc_sa = (incoming or {}).get("social_adaptation")
    if isinstance(inc_sa, dict):
        result["social_adaptation"] = {
            "active": bool(inc_sa.get("active")),
            "reason": inc_sa.get("reason"),
            "level": inc_sa.get("level", "inactive"),
        }
    else:
        result["social_adaptation"] = (
            carried.get("social_adaptation") or BASE_METRICS["social_adaptation"]
        )

    inc_dt = (incoming or {}).get("dominant_trait")
    if isinstance(inc_dt, dict):
        result["dominant_trait"] = {
            "detected": bool(inc_dt.get("detected")),
            "influence": inc_dt.get("influence"),
            "risk": inc_dt.get("risk"),
            "stability_delta": float(inc_dt.get("stability_delta") or 0.0),
            "hint": inc_dt.get("hint"),
            "steps": list(inc_dt.get("steps") or []) if isinstance(inc_dt.get("steps"), list) else [],
        }
    else:
        result["dominant_trait"] = (
            carried.get("dominant_trait") or BASE_METRICS["dominant_trait"]
        )

    inc_ideas = (incoming or {}).get("ideas")
    if isinstance(inc_ideas, list):
        existing = list(carried.get("ideas") or [])
        seen = set(i.get("id") for i in existing if isinstance(i, dict))
        for it in inc_ideas:
            if isinstance(it, dict) and it.get("id") and it["id"] not in seen:
                existing.append(it)
                seen.add(it["id"])
        result["ideas"] = existing
    else:
        result["ideas"] = carried.get("ideas") or []

    result["dimension"] = (incoming or {}).get("dimension", carried.get("dimension"))
    result["priority_drift"] = (incoming or {}).get("priority_drift", carried.get("priority_drift"))
    result["mood_board"] = (incoming or {}).get("mood_board", carried.get("mood_board"))

    inc_pass = (incoming or {}).get("passport") or {}
    car_pass = carried.get("passport") or {}
    merged_pass = {**BASE_METRICS["passport"], **car_pass}
    for k, v in inc_pass.items():
        if k == "completion":
            if isinstance(v, (int, float)) and v > (merged_pass.get("completion") or 0):
                merged_pass["completion"] = int(v)
            continue
        if k in ("values", "constraints", "stakeholders", "risks", "metrics"):
            if isinstance(v, list) and v:
                merged_pass[k] = v
        else:
            if v not in (None, "", [], {}):
                merged_pass[k] = v
    result["passport"] = merged_pass

    inc_prof = (incoming or {}).get("profile") or {}
    car_prof = carried.get("profile") or {}
    merged_prof = {**BASE_METRICS["profile"], **car_prof}
    if isinstance(inc_prof.get("values"), dict) and inc_prof["values"]:
        merged_prof["values"] = {
            **merged_prof.get("values", {}),
            **inc_prof["values"],
        }
    for list_key in ("patterns", "distortions", "insights", "skills"):
        old = list(merged_prof.get(list_key) or [])
        new = inc_prof.get(list_key) or []
        if isinstance(new, list):
            seen = set(map(str, old))
            for item in new:
                if str(item) not in seen:
                    old.append(str(item))
                    seen.add(str(item))
            merged_prof[list_key] = old
    if isinstance(inc_prof.get("somatic"), dict):
        merged_som = {**(merged_prof.get("somatic") or {})}
        for k in ("energy", "tension", "focus"):
            v = inc_prof["somatic"].get(k)
            if isinstance(v, (int, float)):
                merged_som[k] = max(0.0, min(1.0, v))
        if inc_prof["somatic"].get("mood"):
            merged_som["mood"] = inc_prof["somatic"]["mood"]
        if inc_prof["somatic"].get("note"):
            merged_som["note"] = inc_prof["somatic"]["note"]
        merged_prof["somatic"] = merged_som
    result["profile"] = merged_prof

    inc_rem = (incoming or {}).get("reminder")
    result["reminder"] = inc_rem if inc_rem is not None else carried.get("reminder")

    inc_art = (incoming or {}).get("artifacts") or []
    car_art = list(carried.get("artifacts") or [])
    seen_ids = set(a.get("id") for a in car_art if isinstance(a, dict))
    for a in inc_art:
        if not isinstance(a, dict):
            continue
        aid = a.get("id")
        if aid and aid not in seen_ids:
            car_art.append(a)
            seen_ids.add(aid)
    result["artifacts"] = car_art

    return result