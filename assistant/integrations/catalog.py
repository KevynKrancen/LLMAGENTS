"""Built-in connector catalog — curated apps that work with one tap/key.

Each entry declares what config it needs; its tools are plain @tool
functions built as closures over that config.
"""

from __future__ import annotations

import json

import httpx
from langchain_core.tools import BaseTool, tool

CATALOG: list[dict] = [
    {
        "app": "weather",
        "title": "Weather",
        "description": "Forecasts anywhere via Open-Meteo. No key needed.",
        "fields": [],
    },
    {
        "app": "telegram",
        "title": "Telegram",
        "description": "Send yourself Telegram messages via a bot.",
        "fields": [
            {"key": "bot_token", "label": "Bot token (from @BotFather)", "secret": True},
            {"key": "chat_id", "label": "Your chat id (from @userinfobot)"},
        ],
    },
    {
        "app": "github",
        "title": "GitHub",
        "description": "Search repos, read and create issues.",
        "fields": [{"key": "token", "label": "Personal access token", "secret": True}],
    },
    {
        "app": "spotify",
        "title": "Spotify",
        "description": "Search tracks/playlists and open them on the phone.",
        "fields": [
            {"key": "client_id", "label": "Client ID"},
            {"key": "client_secret", "label": "Client secret", "secret": True},
        ],
    },
    {
        "app": "notion",
        "title": "Notion (via MCP)",
        "description": "Connect Notion's hosted MCP server.",
        "mcp_url": "https://mcp.notion.com/mcp",
        "fields": [],
    },
]


def load_builtin_tools(app: str, config: dict) -> list[BaseTool]:
    builders = {
        "weather": _weather_tools,
        "telegram": _telegram_tools,
        "github": _github_tools,
        "spotify": _spotify_tools,
    }
    builder = builders.get(app)
    if not builder:
        raise ValueError(f"Unknown catalog app {app!r}")
    return builder(config)


# --- Weather (Open-Meteo, keyless) ------------------------------------------

def _weather_tools(_config: dict) -> list[BaseTool]:
    @tool(parse_docstring=True)
    def get_weather_forecast(place: str, days: int = 3) -> str:
        """Get the weather forecast for a city or place name.

        Args:
            place: City or place, e.g. 'Tel Aviv' or 'Paris'
            days: Days of forecast to return (1-7)

        Returns:
            JSON with current conditions and a daily forecast
        """
        geo = httpx.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": place, "count": 1},
            timeout=20,
        ).json()
        results = geo.get("results") or []
        if not results:
            return json.dumps({"error": f"Unknown place: {place}"})
        location = results[0]
        forecast = httpx.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": location["latitude"],
                "longitude": location["longitude"],
                "current": "temperature_2m,weather_code,wind_speed_10m",
                "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max",
                "forecast_days": min(max(days, 1), 7),
                "timezone": "auto",
            },
            timeout=20,
        ).json()
        return json.dumps(
            {"place": location["name"], "current": forecast.get("current"),
             "daily": forecast.get("daily")}
        )

    return [get_weather_forecast]


# --- Telegram ---------------------------------------------------------------

def _telegram_tools(config: dict) -> list[BaseTool]:
    bot_token, chat_id = config.get("bot_token", ""), config.get("chat_id", "")

    @tool(parse_docstring=True)
    def send_telegram_message(text: str) -> str:
        """Send a Telegram message to the user's own chat via their bot.

        Args:
            text: Message text (supports basic Markdown)

        Returns:
            JSON {sent: true} or an error
        """
        response = httpx.post(
            f"https://api.telegram.org/bot{bot_token}/sendMessage",
            json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"},
            timeout=20,
        )
        return json.dumps({"sent": response.is_success, "detail": response.json()})

    return [send_telegram_message]


# --- GitHub -----------------------------------------------------------------

def _github_tools(config: dict) -> list[BaseTool]:
    headers = {
        "Authorization": f"Bearer {config.get('token', '')}",
        "Accept": "application/vnd.github+json",
    }

    @tool(parse_docstring=True)
    def search_github_repos(query: str, limit: int = 5) -> str:
        """Search GitHub repositories.

        Args:
            query: Search query, e.g. 'ag-ui language:swift'
            limit: Max results (1-10)

        Returns:
            JSON list of {full_name, description, stars, url}
        """
        data = httpx.get(
            "https://api.github.com/search/repositories",
            params={"q": query, "per_page": min(max(limit, 1), 10)},
            headers=headers,
            timeout=20,
        ).json()
        return json.dumps(
            [
                {"full_name": r["full_name"], "description": r.get("description"),
                 "stars": r["stargazers_count"], "url": r["html_url"]}
                for r in data.get("items", [])
            ]
        )

    @tool(parse_docstring=True)
    def list_github_issues(repo: str, state: str = "open", limit: int = 10) -> str:
        """List issues in a GitHub repository.

        Args:
            repo: 'owner/name', e.g. 'KevynKrancen/LLMAGENTS'
            state: 'open', 'closed', or 'all'
            limit: Max results (1-20)

        Returns:
            JSON list of {number, title, state, url}
        """
        data = httpx.get(
            f"https://api.github.com/repos/{repo}/issues",
            params={"state": state, "per_page": min(max(limit, 1), 20)},
            headers=headers,
            timeout=20,
        ).json()
        if isinstance(data, dict):
            return json.dumps(data)
        return json.dumps(
            [{"number": i["number"], "title": i["title"], "state": i["state"],
              "url": i["html_url"]} for i in data]
        )

    @tool(parse_docstring=True)
    def create_github_issue(repo: str, title: str, body: str = "") -> str:
        """Create an issue in a GitHub repository. Confirm with the user first.

        Args:
            repo: 'owner/name'
            title: Issue title
            body: Issue body (Markdown)

        Returns:
            JSON {number, url} of the created issue
        """
        response = httpx.post(
            f"https://api.github.com/repos/{repo}/issues",
            json={"title": title, "body": body},
            headers=headers,
            timeout=20,
        )
        data = response.json()
        return json.dumps({"number": data.get("number"), "url": data.get("html_url"),
                           "status": response.status_code})

    return [search_github_repos, list_github_issues, create_github_issue]


# --- Spotify ----------------------------------------------------------------

def _spotify_tools(config: dict) -> list[BaseTool]:
    client_id = config.get("client_id", "")
    client_secret = config.get("client_secret", "")

    def _token() -> str:
        response = httpx.post(
            "https://accounts.spotify.com/api/token",
            data={"grant_type": "client_credentials"},
            auth=(client_id, client_secret),
            timeout=20,
        )
        return response.json().get("access_token", "")

    @tool(parse_docstring=True)
    def search_spotify(query: str, kind: str = "track", limit: int = 5) -> str:
        """Search Spotify for tracks, artists, albums, or playlists.

        After finding a match, use open_iphone_app with its spotify_uri as
        deep_link to open it on the phone.

        Args:
            query: What to search for
            kind: 'track', 'artist', 'album', or 'playlist'
            limit: Max results (1-10)

        Returns:
            JSON list of {name, artist, spotify_uri, url}
        """
        data = httpx.get(
            "https://api.spotify.com/v1/search",
            params={"q": query, "type": kind, "limit": min(max(limit, 1), 10)},
            headers={"Authorization": f"Bearer {_token()}"},
            timeout=20,
        ).json()
        items = data.get(f"{kind}s", {}).get("items", [])
        return json.dumps(
            [
                {
                    "name": item.get("name"),
                    "artist": (item.get("artists") or [{}])[0].get("name")
                    if kind in {"track", "album"} else None,
                    "spotify_uri": item.get("uri"),
                    "url": item.get("external_urls", {}).get("spotify"),
                }
                for item in items
                if item
            ]
        )

    return [search_spotify]
