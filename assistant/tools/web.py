"""Web research tools — Tavily search and page fetching."""

from __future__ import annotations

import json

import httpx
from langchain_core.tools import tool

from ..config import settings

_TAVILY_URL = "https://api.tavily.com/search"


@tool(parse_docstring=True, handle_tool_error=True)
def search_web(query: str, max_results: int = 5, topic: str = "general") -> str:
    """Search the live web and return ranked results with content snippets.

    Use for any question about current events, facts you are unsure of,
    prices, weather, news, or anything after your training cutoff.

    Args:
        query: Natural-language search query
        max_results: Number of results to return (1-10)
        topic: Search vertical — 'general', 'news', or 'finance'

    Returns:
        JSON with an 'answer' summary and a 'results' list of
        {title, url, content, score}
    """
    if not settings.tavily_api_key:
        return json.dumps({"error": "TAVILY_API_KEY is not configured."})
    response = httpx.post(
        _TAVILY_URL,
        json={
            "api_key": settings.tavily_api_key,
            "query": query,
            "max_results": min(max(max_results, 1), 10),
            "topic": topic,
            "include_answer": True,
        },
        timeout=30,
    )
    response.raise_for_status()
    data = response.json()
    return json.dumps(
        {
            "answer": data.get("answer"),
            "results": [
                {
                    "title": r["title"],
                    "url": r["url"],
                    "content": r.get("content", "")[:800],
                    "score": r.get("score"),
                }
                for r in data.get("results", [])
            ],
        }
    )


@tool(parse_docstring=True, handle_tool_error=True)
def fetch_web_page(url: str, max_chars: int = 6000) -> str:
    """Download a single web page and return its readable text content.

    Use after search_web when a result needs to be read in full.

    Args:
        url: Absolute http(s) URL of the page to fetch
        max_chars: Truncate the extracted text to this many characters

    Returns:
        Plain text content of the page, truncated to max_chars
    """
    response = httpx.get(
        url,
        timeout=30,
        follow_redirects=True,
        headers={"User-Agent": "Mozilla/5.0 (Hermes Assistant)"},
    )
    response.raise_for_status()
    try:
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(response.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        text = " ".join(soup.get_text(separator=" ").split())
    except ImportError:
        text = response.text
    return text[:max_chars]
