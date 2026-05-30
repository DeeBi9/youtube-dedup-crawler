# RESULTS — Task 5

## Live URL ()
[LIVE URL](https://youtube-dedup-crawler.onrender.com)

Here '/' endpoint will show : `detail:	"Not Found"`

But two endpoints are clear : `1./health `
                              `2./queue `

## Setup
- Keyword crawled: dheera dheera song
- Interval: 60 minutes (5 minutes during testing, increased to 60 minutes after validation to reduce YouTube API quota usage)
- Queue store (Redis / in-memory): In-memory queue
- Persistence (DB used): SQLite (crawler.db)

## Crawl run
- How long it ran: Multiple scheduled crawls over approximately 20–30 minutes during testing, then deployed to Render for continuous scheduled execution.
- Total results seen: 422 results across multiple paginated crawls.
- Unique items queued (after dedup): 311

## Dedup proof (the important part)
- The re-upload example: two videos that are the same content at different URLs
  - URL A: https://www.youtube.com/watch?v=IuS4LL_ALrU
  - URL B: https://www.youtube.com/watch?v=8vtJB6dZEIg
  - pHash A: 888716396bf63762
  - pHash B: 88c716396bd63363
  - Hamming distance: 4
  - Was B correctly skipped? (yes/no): yes
  - Video 1 Thumbnail : ![](<Screenshot from 2026-05-31 02-03-46.png>)
  - Video 2 Thumbnail : ![](image.png)

## VISUAL VERIFICATION 
The duplicate candidate was manually reviewed.

Observations:

- Both videos contained the Kannada version of the song "Dheera Dheera" from KGF.
- The videos were uploaded under different YouTube URLs and appeared as separate uploads.
- The thumbnails were visually identical.
- One upload showed approximately 24M views while the other showed approximately 4M views at the time of testing.
- The computed pHashes differed by only 4 bits (Hamming distance = 4).
- Since the distance was below the configured threshold (5), the second upload was correctly classified as a duplicate and skipped.

  Screenshot 1 : ![](images/image1.png)

  Screenshot 2 : ![](images/image2.png)

## Rate limit / pagination handling

- Pagination was implemented using YouTube's `nextPageToken`.
- The crawler continues requesting pages until `nextPageToken` becomes `None`.
- During testing, multiple paginated crawls successfully traversed up to 12 pages of search results.
- HTTP 403 quota-exceeded responses are detected and logged, after which pagination stops gracefully.
- HTTP 429 rate-limit responses are detected using the `Retry-After` header.
- On the first 429 response, the crawler waits for the specified retry duration and retries the same page once.
- If rate limiting persists, the crawl is aborted gracefully to avoid excessive API usage.

## Anything that broke / would improve with more time

- The free YouTube Data API quota (10,000 units/day) was exhausted during testing because search pagination consumes quota quickly.
- With more time, I would add quota-aware crawl limits and persistent queue storage using Redis instead of an in-memory queue.

