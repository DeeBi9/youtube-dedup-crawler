"""
Task 5 — Keyword Crawler + Dedup
"""
from collections import deque
from datetime import datetime
from itertools import count

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI, HTTPException
from sqlalchemy import func
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

_crawl_counter = count(1)


def _ts():
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


def log_page(crawl_id, page_number, next_page_token, results_this_page):
    with open("pagination.log", "a") as f:
        f.write(
            f"[{_ts()}]\n"
            f"CRAWL={crawl_id}\n"
            f"PAGE={page_number}\n"
            f"NEXT_PAGE_TOKEN={next_page_token}\n"
            f"RESULTS={results_this_page}\n\n"
        )


def log_video(crawl_id, video_id, title, phash, status):
    with open("crawl.log", "a") as f:
        f.write(
            f"[{_ts()}]\n"
            f"CRAWL={crawl_id}\n"
            f"VIDEO_ID={video_id}\n"
            f"TITLE={title}\n"
            f"PHASH={phash}\n"
            f"STATUS={status}\n\n"
        )


def log_duplicate(crawl_id, video_id, title, url, new_phash,
                   matched_video_id, matched_title, matched_url, matched_phash, distance):
    with open("dedup.log", "a") as f:
        f.write(
            f"[{_ts()}]\n"
            f"CRAWL={crawl_id}\n"
            f"NEW_VIDEO_ID={video_id}\n"
            f"NEW_TITLE={title}\n"
            f"NEW_URL={url}\n"
            f"NEW_PHASH={new_phash}\n"
            f"\n"
            f"MATCHED_VIDEO_ID={matched_video_id}\n"
            f"MATCHED_TITLE={matched_title}\n"
            f"MATCHED_URL={matched_url}\n"
            f"MATCHED_PHASH={matched_phash}\n"
            f"\n"
            f"HAMMING_DISTANCE={distance}\n"
            f"THRESHOLD={PHASH_THRESHOLD}\n"
            f"SKIPPED=yes\n\n"
        )


def log_growth(crawl_id, new_items, duplicates, total_rows):
    with open("queue_growth.log", "a") as f:
        f.write(
            f"[{_ts()}]\n"
            f"CRAWL={crawl_id}\n"
            f"NEW_ITEMS={new_items}\n"
            f"DUPLICATES={duplicates}\n"
            f"TOTAL_QUEUE_ROWS={total_rows}\n\n"
        )


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
    crawl_id = next(_crawl_counter)
    print(f"SCHEDULER | crawl_started | crawl_id={crawl_id} | interval={INTERVAL_MIN}min")
    try:
        crawl_once(crawl_id)
    except Exception as e:
        print(f"SCHEDULER | crawl_failed | crawl_id={crawl_id} | error={e}")
        raise
    print(f"SCHEDULER | crawl_completed | crawl_id={crawl_id}")


def crawl_once(crawl_id):
    engine = get_engine()
    page_token = None
    page_number = 0
    total_new = 0
    total_dupes = 0
    total_skipped_thumb = 0

    while True:
        result = search_videos(YT_API_KEY, KEYWORD, page_token=page_token, max_results=50)

        if not result["success"]:
            if result["error"] == "quota_exceeded":
                print(f"QUOTA | {result['message']} | new_so_far={total_new}")
            elif result["error"] == "rate_limited":
                retry = result.get("retry_after")
                print(f"RATE_LIMIT | retry_after={retry} | new_so_far={total_new}")
            else:
                print(f"ERROR | {result['error']} | {result['message']}")
            break

        page_number += 1
        items = result["items"]
        next_page_token = result["next_page_token"]
        print(f"PAGINATION | page={page_number} | next_page_token={next_page_token} | results_this_page={len(items)}")
        log_page(crawl_id, page_number, next_page_token, len(items))

        with Session(engine) as session:
            for item in items:
                video_id = item["video_id"]
                title = item["title"]

                thumb_bytes = download_thumbnail(item["thumbnail_url"])
                if thumb_bytes is None:
                    total_skipped_thumb += 1
                    log_video(crawl_id, video_id, title, "N/A", "THUMBNAIL_FAILED")
                    print(f"ERROR | skip_video_id={video_id} | reason=thumbnail_fetch_failed | title={title}")
                    continue

                phash = compute_phash(thumb_bytes)
                print(f"PHASH | video_id={video_id} | phash={phash}")

                is_dupe, matched_phash, dist, matched_id, matched_title, matched_url = \
                    check_duplicate(phash, phash_cache, PHASH_THRESHOLD)
                if is_dupe:
                    total_dupes += 1
                    log_duplicate(
                        crawl_id, video_id, title, item["url"], str(phash),
                        matched_id, matched_title, matched_url, str(matched_phash), dist,
                    )
                    log_video(crawl_id, video_id, title, str(phash), "DUPLICATE")
                    print(f"DUPLICATE | new_video_id={video_id} | matched_video_id={matched_id} | hamming={dist} | threshold={PHASH_THRESHOLD} | skipped=yes")
                    continue

                session.add(ScanQueue(
                    video_id=video_id,
                    title=title,
                    url=item["url"],
                    thumbnail=item["thumbnail_url"],
                    phash=str(phash),
                ))
                session.commit()
                phash_cache.add(phash, video_id, title, item["url"])
                queue.append(item)
                total_new += 1
                log_video(crawl_id, video_id, title, str(phash), "NEW")
                print(f"NEW | video_id={video_id} | title={title} | phash={phash}")

        if not next_page_token:
            break
        page_token = next_page_token

    with Session(engine) as session:
        total_rows = session.query(func.count(ScanQueue.id)).scalar()

    log_growth(crawl_id, total_new, total_dupes, total_rows)
    print(f"CRAWL | keyword=\"{KEYWORD}\" | pages={page_number} | new={total_new} | duplicates={total_dupes} | thumbnail_skipped={total_skipped_thumb} | total_rows={total_rows}")


@app.on_event("startup")
def on_startup():
    global scheduler, phash_cache

    init_db()
    print("STARTUP | db_initialized")

    loaded = load_all_phashes()
    for phash, video_id, title, url in loaded:
        phash_cache.add(phash, video_id, title, url)
    print(f"STARTUP | phash_cache_loaded | count={len(phash_cache)} | threshold={PHASH_THRESHOLD}")

    _scheduled_crawl()

    scheduler = BackgroundScheduler()
    scheduler.add_job(
        _scheduled_crawl,
        trigger="interval",
        minutes=INTERVAL_MIN,
        id="crawl_once",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    scheduler.start()
    print(f"SCHEDULER | started | interval={INTERVAL_MIN}min | job_id=crawl_once | max_instances=1 | coalesce=True")


@app.on_event("shutdown")
def on_shutdown():
    global scheduler
    if scheduler and scheduler.running:
        scheduler.shutdown(wait=False)
        print("SCHEDULER | shutdown")
