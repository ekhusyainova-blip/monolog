@app.get("/code/read")
async def code_read(path: str, branch: str = ""):
    r = await _gh_get(f"contents/{path}", branch)
    if r.status_code == 404:
        return JSONResponse({"exists": False, "path": path})
    if r.status_code >= 400:
        raise HTTPException(status_code=502, detail=f"GitHub: {r.status_code}")
    data = r.json()
    try:
        content = base64.b64decode(data.get("content", "")).decode("utf-8")
    except Exception:
        content = ""
    return JSONResponse({"exists": True, "path": path, "sha": data.get("sha"), "content": content})