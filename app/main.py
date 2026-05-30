"""
Task 5 — Keyword Crawler + Dedup
Fill in the TODOs. Keep the endpoint contracts as-is.
"""
from fastapi import FastAPI

from .config import load_config
from .database import init_db

app = FastAPI(title="Keyword Crawler + Dedup")

config = load_config()
KEYWORD = config["KEYWORD"]
INTERVAL_MIN = config["INTERVAL_MIN"]
PHASH_THRESHOLD = config["PHASH_THRESHOLD"]


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/queue")
def get_queue():
    """Return the current scan_queue (the new, de-duplicated items found so far)."""
    return {"count": 0, "items": []}


def crawl_once():
    """
    Runs every INTERVAL_MIN minutes (wire this into APScheduler on startup):
      1. query YouTube Data API v3 for KEYWORD  (handle pagination + quota)
      2. for each video: fetch thumbnail, compute pHash
      3. dedup against everything seen (perceptual, not exact-URL)
      4. push NEW items to queue + persist to scan_queue
    """
    pass


@app.on_event("startup")
def on_startup():
    init_db()


@app.on_event("shutdown")
def on_shutdown():
    pass
