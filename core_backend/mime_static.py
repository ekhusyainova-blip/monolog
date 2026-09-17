# core_backend/mime_static.py
# Кастомный StaticFiles: MIME по расширению, без mimetypes Python.

from starlette.staticfiles import StaticFiles
import os


MIME_MAP = {
    ".js":   "application/javascript; charset=utf-8",
    ".mjs":  "application/javascript; charset=utf-8",
    ".css":  "text/css; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".html": "text/html; charset=utf-8",
    ".htm":  "text/html; charset=utf-8",
    ".svg":  "image/svg+xml",
    ".png":  "image/png",
    ".jpg":  "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif":  "image/gif",
    ".ico":  "image/x-icon",
    ".woff": "font/woff",
    ".woff2": "font/woff2",
    ".ttf":  "font/ttf",
    ".txt":  "text/plain; charset=utf-8",
    ".md":   "text/markdown; charset=utf-8",
}


def guess_mime(path: str) -> str:
    _, ext = os.path.splitext(path.lower())
    return MIME_MAP.get(ext, "application/octet-stream")


class MimeStaticFiles(StaticFiles):
    async def get_response(self, path, scope):
        response = await super().get_response(path, scope)
        if response.status_code == 200:
            scope_path = scope.get("path", "")
            response.headers["content-type"] = guess_mime(scope_path)
        return response
    