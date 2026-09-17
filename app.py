# app.py (заглушка)
# Временный минимальный backend. Заменяет сломанный монолит.
# Цель: Render запускается, /health работает, /docs доступен.
# Дальше — модули из core_backend/ и новый app.py.

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Monolog (stub)")

app.mount("/core", StaticFiles(directory="core"), name="core")
app.mount("/adaptive", StaticFiles(directory="adaptive"), name="adaptive")
app.mount("/public", StaticFiles(directory="public"), name="public")
app.mount("/blog", StaticFiles(directory="blog"), name="blog")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    return FileResponse("index.html")


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "version": "stub",
        "mode": "заглушка",
        "note": "app.py заменён на заглушку. Модули будут залиты позже.",
    }


if __name__ == "__main__":
    import uvicorn
    import os
    uvicorn.run("app:app", host="0.0.0.0", port=int(os.getenv("PORT", 8000)))