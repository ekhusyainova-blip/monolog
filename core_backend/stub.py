# core_backend/stub.py
# Заглушка Monolog. Активируется через APP_MODE=stub.

import os
from fastapi import FastAPI
from fastapi.responses import FileResponse
from core_backend.mime_static import MimeStaticFiles
from fastapi.middleware.cors import CORSMiddleware

from core_backend.stub_endpoints import router as stub_router


app = FastAPI(title="Monolog (stub)")

app.mount("/core", MimeStaticFiles(directory="core"), name="core")
app.mount("/adaptive", MimeStaticFiles(directory="adaptive"), name="adaptive")
app.mount("/blog", MimeStaticFiles(directory="blog"), name="blog")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

app.include_router(stub_router)


@app.get("/")
async def root():
    return FileResponse("index.html")


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "version": "stub+ai",
        "app_mode": "stub",
        "mode": "заглушка (core_backend/stub.py)",
    }