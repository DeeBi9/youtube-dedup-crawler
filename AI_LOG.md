# AI_LOG — Task 5

## Tools used

* ChatGPT
* DeepSeek
* Cursor

## Most useful prompts

* "Review my scheduler implementation and check if overlapping crawls are possible."
* "Verify that pagination is working correctly with YouTube nextPageToken."
* "Help debug YouTube API quota and rate-limit issues on Render."
* "Review my pHash deduplication logic and threshold choice."

## Where the AI was WRONG / gave broken output, and how you caught it

* At one point AI suggested that Render networking or deployment issues were causing crawl failures. After checking Google Cloud quota metrics, I found that the actual problem was that my YouTube API daily quota had been exhausted.
* Some responses assumed pagination was broken, but after checking the logs I confirmed that multiple pages were being fetched correctly through nextPageToken.
* AI-generated estimates of crawl counts were not always accurate, so I relied on actual deployment logs, queue counts, and database records when filling the final results.

## Design decisions you made (2-3 lines each, why)

### Scheduler choice

I used APScheduler because it was simple to integrate with FastAPI and worked well for recurring crawls. I added `max_instances=1` and `coalesce=True` to avoid overlapping crawls after noticing that long-running crawls could trigger concurrent executions.

### Dedup / pHash approach + distance threshold

I used perceptual hashing instead of URL matching because the goal was to catch re-uploads of the same content. After testing with real examples, I used a Hamming distance threshold of 5, which successfully detected visually identical thumbnails uploaded under different URLs.

### Queue + persistence choice

I used an in-memory queue for fast access through the API and SQLite for persistence. SQLite was enough for this assignment and made deployment simpler than introducing an external database.
