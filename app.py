# app.py
# Точка входа Monolog.
# Переключатель APP_MODE: 'stub' — заглушка, 'full' — полный backend.

import os
import mimetypes

# Регистрируем MIME-типы до импорта StaticFiles
mimetypes.add_type("application/javascript", ".js")
mimetypes.add_type("text/css", ".css")
mimetypes.add_type("application/json", ".json")
mimetypes.add_type("image/svg+xml", ".svg")
mimetypes.add_type("text/html", ".html")

APP_MODE = os.getenv("APP_MODE", "stub").strip().lower()


if APP_MODE == "stub":
    from core_backend.stub import app

elif APP_MODE == "full":
    from core_backend.full_app import app

else:
    raise RuntimeError(f"APP_MODE='{APP_MODE}' — неизвестное значение. Используй 'stub' или 'full'.")

# --- /report (от стартера) ---

REPORTS = []


class ReportBody(BaseModel):
    t: str = ""
    level: str = ""
    cycles_done: int = 0
    went_to: str = ""
    last_result: str = ""
    emergency: bool = False
    reason: str = ""


@app.post("/report")
async def report_add(body: ReportBody):
    entry = {
        "t": body.t,
        "level": body.level,
        "cycles_done": body.cycles_done,
        "went_to": body.went_to,
        "last_result": body.last_result,
        "emergency": body.emergency,
        "reason": body.reason,
    }
    REPORTS.insert(0, entry)
    del REPORTS[200:]

    if body.emergency:
        STATE["errors"].insert(0, entry)
        del STATE["errors"][20:]

    return {"ok": True}


@app.get("/reports")
async def reports_get():
    return {"reports": REPORTS}
    
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=int(os.getenv("PORT", 8000)))