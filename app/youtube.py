import httpx

YT_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"


def search_videos(api_key, keyword, page_token=None, max_results=50):
    params = {
        "part": "snippet",
        "q": keyword,
        "type": "video",
        "maxResults": min(max_results, 50),
        "key": api_key,
    }
    if page_token:
        params["pageToken"] = page_token

    try:
        response = httpx.get(YT_SEARCH_URL, params=params, timeout=15)
    except httpx.TimeoutException:
        return {"success": False, "error": "timeout", "message": "YouTube API request timed out"}
    except httpx.RequestError as e:
        return {"success": False, "error": "request_failed", "message": str(e)}

    if response.status_code == 200:
        data = response.json()
        items = []
        for item in data.get("items", []):
            if item.get("id", {}).get("kind") != "youtube#video":
                continue
            video_id = item["id"]["videoId"]
            snippet = item.get("snippet", {})
            thumbnails = snippet.get("thumbnails", {})
            thumbnail_url = (
                thumbnails.get("high", {}).get("url")
                or thumbnails.get("medium", {}).get("url")
                or thumbnails.get("default", {}).get("url")
            )
            items.append({
                "video_id": video_id,
                "title": snippet.get("title", ""),
                "url": f"https://www.youtube.com/watch?v={video_id}",
                "thumbnail_url": thumbnail_url,
            })
        page_info = data.get("pageInfo", {})
        return {
            "success": True,
            "items": items,
            "next_page_token": data.get("nextPageToken"),
            "page_info": {
                "total_results": page_info.get("totalResults"),
                "results_per_page": page_info.get("resultsPerPage"),
            },
        }

    if response.status_code == 403:
        body = response.json()
        reasons = []
        for error in body.get("error", {}).get("errors", []):
            reasons.append(error.get("reason", ""))
        if "quotaExceeded" in reasons:
            return {"success": False, "error": "quota_exceeded", "message": "YouTube API quota exceeded"}
        return {"success": False, "error": "forbidden", "message": body.get("error", {}).get("message", "Forbidden")}

    if response.status_code == 429:
        retry_after = response.headers.get("Retry-After")
        try:
            retry_after = int(retry_after)
        except (ValueError, TypeError):
            retry_after = None
        return {
            "success": False,
            "error": "rate_limited",
            "message": "YouTube API rate limit exceeded",
            "retry_after": retry_after,
        }

    return {"success": False, "error": f"http_{response.status_code}", "message": response.text}


def download_thumbnail(url, timeout=10):
    try:
        resp = httpx.get(url, timeout=timeout)
        if resp.status_code == 200:
            return resp.content
    except (httpx.TimeoutException, httpx.RequestError):
        pass
    return None
