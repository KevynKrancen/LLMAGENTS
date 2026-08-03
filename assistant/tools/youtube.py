"""YouTube tools — search for videos so the iPhone can play them.

Playback itself happens ON the phone via the device tool
``play_youtube_video`` (declared in device.py, executed by the iOS app).
Typical flow: search_youtube_videos → pick best match → play_youtube_video.
"""

from __future__ import annotations

import json

import httpx
from langchain_core.tools import tool

from ..config import settings

_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"


@tool(parse_docstring=True, handle_tool_error=True)
def search_youtube_videos(query: str, max_results: int = 5) -> str:
    """Search YouTube and return matching videos with their video ids.

    After finding the right video, call the device tool play_youtube_video
    with its video_id to open and play it on the user's iPhone.

    Args:
        query: What to search for, e.g. 'lofi hip hop radio' or an artist + song
        max_results: Number of results to return (1-10)

    Returns:
        JSON list of {video_id, title, channel, url}
    """
    if not settings.youtube_api_key:
        return json.dumps(
            {"error": "YOUTUBE_API_KEY is not configured — falling back: call "
                      "play_youtube_search on the device with the raw query instead."}
        )
    response = httpx.get(
        _SEARCH_URL,
        params={
            "key": settings.youtube_api_key,
            "q": query,
            "part": "snippet",
            "type": "video",
            "maxResults": min(max(max_results, 1), 10),
        },
        timeout=30,
    )
    response.raise_for_status()
    items = response.json().get("items", [])
    return json.dumps(
        [
            {
                "video_id": item["id"]["videoId"],
                "title": item["snippet"]["title"],
                "channel": item["snippet"]["channelTitle"],
                "url": f"https://www.youtube.com/watch?v={item['id']['videoId']}",
            }
            for item in items
        ]
    )
