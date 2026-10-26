
import html
import time
from typing import Any

import requests
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("WeekendWizardTools")

HTTP = requests.Session()
HTTP.headers.update({"User-Agent": "WeekendWizardLocalAgent/1.0"})
TIMEOUT = 15


def api_get(url: str, params: dict | None = None) -> dict[str, Any]:
    last_error = "Unknown API error"

    for attempt in range(2):
        try:
            response = HTTP.get(url, params=params, timeout=TIMEOUT)
            response.raise_for_status()
            data = response.json()

            if not isinstance(data, dict):
                raise ValueError("The API returned an unexpected response.")

            return data

        except (requests.RequestException, ValueError) as exc:
            last_error = str(exc)
            if attempt == 0:
                time.sleep(0.5)

    raise RuntimeError(f"API request failed: {last_error}")


@mcp.tool()
def city_to_coords(city: str) -> dict[str, Any]:
    """Find a city's latitude and longitude using Open-Meteo geocoding."""
    city = city.strip()
    if not city or len(city) > 120:
        return {"error": "Enter a valid city name."}

    data = api_get(
        "https://geocoding-api.open-meteo.com/v1/search",
        {"name": city, "count": 5, "language": "en", "format": "json"},
    )

    results = data.get("results", [])
    if not results:
        return {"error": f"No location found for '{city}'."}

    places = []
    for item in results:
        places.append({
            "name": item.get("name"),
            "admin1": item.get("admin1"),
            "country": item.get("country"),
            "latitude": item.get("latitude"),
            "longitude": item.get("longitude"),
        })

    return {"query": city, "locations": places}


@mcp.tool()
def get_weather(latitude: float, longitude: float) -> dict[str, Any]:
    """Get current weather, temperature, and wind speed for coordinates."""
    if not (-90 <= latitude <= 90):
        return {"error": "Latitude must be between -90 and 90."}
    if not (-180 <= longitude <= 180):
        return {"error": "Longitude must be between -180 and 180."}

    data = api_get(
        "https://api.open-meteo.com/v1/forecast",
        {
            "latitude": latitude,
            "longitude": longitude,
            "current": (
                "temperature_2m,relative_humidity_2m,"
                "apparent_temperature,is_day,precipitation,"
                "weather_code,wind_speed_10m"
            ),
            "timezone": "auto",
        },
    )

    current = data.get("current")
    if not current:
        return {"error": "Current weather data was not returned."}

    return {
        "latitude": latitude,
        "longitude": longitude,
        "timezone": data.get("timezone"),
        "current": current,
        "source": "https://open-meteo.com/",
    }


@mcp.tool()
def book_recs(topic: str, limit: int = 5) -> dict[str, Any]:
    """Recommend books by topic, genre, or subject using Open Library."""
    topic = topic.strip()
    if not topic or len(topic) > 160:
        return {"error": "Enter a valid book topic."}

    limit = max(1, min(int(limit), 10))
    data = api_get(
        "https://openlibrary.org/search.json",
        {"q": topic, "limit": limit, "fields": "title,author_name,first_publish_year,key"},
    )

    books = []
    for item in data.get("docs", [])[:limit]:
        title = item.get("title")
        if not title:
            continue

        work_key = item.get("key", "")
        books.append({
            "title": title,
            "author": (item.get("author_name") or ["Unknown author"])[0],
            "first_publish_year": item.get("first_publish_year"),
            "url": f"https://openlibrary.org{work_key}" if work_key else None,
        })

    return {"topic": topic, "books": books}


@mcp.tool()
def random_joke() -> dict[str, Any]:
    """Get one safe, single-line joke."""
    data = api_get(
        "https://v2.jokeapi.dev/joke/Any",
        {"type": "single", "safe-mode": ""},
    )

    if data.get("error"):
        return {"error": "The joke service could not provide a joke."}

    joke = data.get("joke")
    if not joke:
        return {"error": "No joke was returned."}

    return {"joke": joke, "source": "https://jokeapi.dev/"}


@mcp.tool()
def random_dog() -> dict[str, Any]:
    """Get a random dog photo URL from Dog CEO."""
    data = api_get("https://dog.ceo/api/breeds/image/random")

    if data.get("status") != "success" or not data.get("message"):
        return {"error": "The dog photo service returned no image."}

    return {
        "image_url": data["message"],
        "source": "https://dog.ceo/dog-api/",
    }


@mcp.tool()
def trivia() -> dict[str, Any]:
    """Get one multiple-choice trivia question and its answer."""
    data = api_get(
        "https://opentdb.com/api.php",
        {"amount": 1, "type": "multiple"},
    )

    results = data.get("results", [])
    if not results:
        return {"error": "No trivia question is available right now."}

    item = results[0]
    return {
        "category": html.unescape(item.get("category", "")),
        "difficulty": item.get("difficulty", ""),
        "question": html.unescape(item.get("question", "")),
        "correct_answer": html.unescape(item.get("correct_answer", "")),
        "incorrect_answers": [
            html.unescape(answer)
            for answer in item.get("incorrect_answers", [])
        ],
        "source": "https://opentdb.com/",
    }


if __name__ == "__main__":
    mcp.run(transport="stdio")
