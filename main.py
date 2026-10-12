"""Zero-knowledge file share: storage server.

The server only ever sees encrypted bytes. The AES key lives in the share
link's #fragment, which browsers never send over the network.
"""
import json
import os
import re
import secrets
import threading
import time
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, Response

STORAGE = Path(os.getenv("STORAGE_DIR", "storage"))
MAX_BYTES = 25 * 1024 * 1024        # 25 MB per upload
MAX_TTL = 7 * 24 * 3600             # links live at most 7 days
RATE_LIMIT, RATE_WINDOW = 20, 60    # 20 requests per IP per minute
STATIC = Path(__file__).parent / "static"
ID_RE = re.compile(r"^[0-9a-f]{32}$")

app = FastAPI(title="Zero-knowledge file share")
_lock = threading.Lock()
_hits: dict[str, list[float]] = {}


def _paths(fid: str):
    return STORAGE / f"{fid}.bin", STORAGE / f"{fid}.json"


def _delete(fid: str):
    for p in _paths(fid):
        p.unlink(missing_ok=True)


def _rate_limit(request: Request):
    ip = request.client.host if request.client else "unknown"
    now = time.time()
    recent = [t for t in _hits.get(ip, []) if now - t < RATE_WINDOW]
    if len(recent) >= RATE_LIMIT:
        raise HTTPException(429, "Too many requests. Try again in a minute.")
    recent.append(now)
    _hits[ip] = recent


def _purge_expired():
    now = time.time()
    for meta_path in STORAGE.glob("*.json"):
        try:
            if json.loads(meta_path.read_text())["expires_at"] <= now:
                _delete(meta_path.stem)
        except (OSError, ValueError, KeyError):
            continue


@app.post("/api/files", status_code=201)
async def upload(
    request: Request,
    ttl: int = Query(3600, ge=60, le=MAX_TTL, description="seconds until the link expires"),
    max_downloads: int = Query(1, ge=1, le=100),
):
    _rate_limit(request)
    declared = request.headers.get("content-length")
    if declared and int(declared) > MAX_BYTES:
        raise HTTPException(413, "File too large (limit 25 MB).")
    data = await request.body()
    if not data:
        raise HTTPException(400, "Empty upload.")
    if len(data) > MAX_BYTES:
        raise HTTPException(413, "File too large (limit 25 MB).")

    STORAGE.mkdir(parents=True, exist_ok=True)
    _purge_expired()
    fid = secrets.token_hex(16)
    blob_path, meta_path = _paths(fid)
    meta = {
        "expires_at": time.time() + ttl,
        "max_downloads": max_downloads,
        "downloads": 0,
        "size": len(data),
    }
    blob_path.write_bytes(data)
    meta_path.write_text(json.dumps(meta))
    return {"id": fid, "expires_at": meta["expires_at"], "max_downloads": max_downloads}


@app.get("/api/files/{fid}")
def download(fid: str, request: Request):
    _rate_limit(request)
    if not ID_RE.match(fid):
        raise HTTPException(404, "Not found.")
    blob_path, meta_path = _paths(fid)
    with _lock:  # one download at a time so "one-time" really means one
        try:
            meta = json.loads(meta_path.read_text())
            data = blob_path.read_bytes()
        except (OSError, ValueError):
            raise HTTPException(404, "Not found or already deleted.")
        if meta["expires_at"] <= time.time():
            _delete(fid)
            raise HTTPException(404, "Not found or already deleted.")
        meta["downloads"] += 1
        if meta["downloads"] >= meta["max_downloads"]:
            _delete(fid)
        else:
            meta_path.write_text(json.dumps(meta))
    return Response(
        content=data,
        media_type="application/octet-stream",
        headers={"Cache-Control": "no-store"},
    )


@app.delete("/api/files/{fid}", status_code=204)
def remove(fid: str, request: Request):
    _rate_limit(request)
    if ID_RE.match(fid):
        with _lock:
            _delete(fid)


@app.get("/", include_in_schema=False)
def home_page():
    return FileResponse(STATIC / "index.html")


@app.get("/f/{fid}", include_in_schema=False)
def share_page(fid: str):
    return FileResponse(STATIC / "index.html")