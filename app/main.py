"""
Task 5 — Keyword Crawler + Dedup
"""
from fastapi import FastAPI
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
queue = []


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/queue")
def get_queue():
    return {"count": 0, "items": []}


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
    init_db()
    global phash_cache
    loaded = load_all_phashes()
    for h in loaded:
        phash_cache.add(h)
    print(f"STARTUP | loaded_phashes={len(phash_cache)} | threshold={PHASH_THRESHOLD}")


@app.on_event("shutdown")
def on_shutdown():
    pass
