"""
Task 5 — Keyword Crawler + Dedup
"""
from collections import deque

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI, HTTPException
from sqlalchemy.orm import Session

from .config import load_config
from .database import init_db, get_engine, ScanQueue, load_all_phashes
from .dedup import PhashCache, compute_phash, check_duplicate
from .youtube import search_videos, download_thumbnail

app = FastAPI(title="Keyword Crawler + Dedup")

config = load_config()
YT_API_KEY = config["YT_API_KEY"]
KEYWORD = config["KEYWORD"]
INTERVAL_MIN = config["INTERVAL_MIN"]
PHASH_THRESHOLD = config["PHASH_THRESHOLD"]

phash_cache = PhashCache()
queue = deque(maxlen=1000)
scheduler = None


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/queue")
def get_queue():
    try:
        engine = get_engine()
        with Session(engine) as session:
            rows = (
                session.query(ScanQueue)
                .order_by(ScanQueue.created_at.desc())
                .all()
            )
        items = [
            {
                "video_id": r.video_id,
                "title": r.title,
                "url": r.url,
                "thumbnail": r.thumbnail,
                "phash": r.phash,
                "created_at": r.created_at,
            }
            for r in rows
        ]
        return {"count": len(items), "items": items}
    except Exception as e:
        print(f"ERROR | get_queue | {e}")
        raise HTTPException(status_code=500, detail="Failed to read queue")


def _scheduled_crawl():
    print(f"SCHEDULER | crawl_started | interval={INTERVAL_MIN}min")
    try:
        crawl_once()
    except Exception as e:
        print(f"SCHEDULER | crawl_failed | error={e}")
        raise
    print("SCHEDULER | crawl_completed")


def crawl_once():
    engine = get_engine()
    page_token = None
    page_number = 0
    total_new = 0
    total_dupes = 0
    total_skipped_thumb = 0

    while True:
        result = search_videos(YT_API_KEY, KEYWORD, page_token=page_token, max_results=50)

        if not result["success"]:
            log = f"ERROR | {result['error']} | {result['message']}"
            if result["error"] == "quota_exceeded":
                log += f" | new_so_far={total_new}"
                print(f"QUOTA | {result['message']} | new_so_far={total_new}")
            elif result["error"] == "rate_limited":
                retry = result.get("retry_after")
                log += f" | retry_after={retry}"
            print(log)
            break

        page_number += 1
        items = result["items"]
        next_page_token = result["next_page_token"]
        print(f"PAGINATION | page={page_number} | next_page_token={next_page_token} | results_this_page={len(items)}")

        with Session(engine) as session:
            for item in items:
                video_id = item["video_id"]

                thumb_bytes = download_thumbnail(item["thumbnail_url"])
                if thumb_bytes is None:
                    total_skipped_thumb += 1
                    print(f"ERROR | skip_video_id={video_id} | reason=thumbnail_fetch_failed | title={item['title']}")
                    continue

                phash = compute_phash(thumb_bytes)
                print(f"PHASH | video_id={video_id} | phash={phash}")

                is_dupe, matched, dist = check_duplicate(phash, phash_cache, PHASH_THRESHOLD)
                if is_dupe:
                    total_dupes += 1
                    print(f"DUPLICATE | new_video_id={video_id} | existing_phash={matched} | hamming={dist} | threshold={PHASH_THRESHOLD} | skipped=yes")
                    continue

                session.add(ScanQueue(
                    video_id=video_id,
                    title=item["title"],
                    url=item["url"],
                    thumbnail=item["thumbnail_url"],
                    phash=str(phash),
                ))
                session.commit()
                phash_cache.add(phash)
                queue.append(item)
                total_new += 1
                print(f"NEW | video_id={video_id} | title={item['title']} | phash={phash}")

        if not next_page_token:
            break
        page_token = next_page_token

    print(f"CRAWL | keyword=\"{KEYWORD}\" | pages={page_number} | new={total_new} | duplicates={total_dupes} | thumbnail_skipped={total_skipped_thumb}")


@app.on_event("startup")
def on_startup():
    global scheduler, phash_cache

    init_db()
    print("STARTUP | db_initialized")

    loaded = load_all_phashes()
    for h in loaded:
        phash_cache.add(h)
    print(f"STARTUP | phash_cache_loaded | count={len(phash_cache)} | threshold={PHASH_THRESHOLD}")

    scheduler = BackgroundScheduler()
    scheduler.add_job(
        _scheduled_crawl,
        trigger="interval",
        minutes=INTERVAL_MIN,
        id="crawl_once",
        replace_existing=True,
    )
    scheduler.start()
    print(f"SCHEDULER | started | interval={INTERVAL_MIN}min | job_id=crawl_once")

    _scheduled_crawl()


@app.on_event("shutdown")
def on_shutdown():
    global scheduler
    if scheduler and scheduler.running:
        scheduler.shutdown(wait=False)
        print("SCHEDULER | shutdown")
