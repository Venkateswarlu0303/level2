import html
import json
import os
import random
import requests
from ollama import Client
from prompt import SYSTEM_PROMPT, REFLECTION_PROMPT

MODEL_NAME = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
client = Client(host=OLLAMA_HOST)

TIMEOUT = 15
MAX_STEPS = 6

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "get_weather_by_city",
            "description": "Get current weather for a city.",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {"type": "string"}
                },
                "required": ["city"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get current weather using latitude and longitude.",
            "parameters": {
                "type": "object",
                "properties": {
                    "latitude": {"type": "number"},
                    "longitude": {"type": "number"}
                },
                "required": ["latitude", "longitude"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "book_recs",
            "description": "Find book recommendations by topic.",
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {"type": "string"},
                    "limit": {"type": "integer"}
                },
                "required": ["topic"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "random_joke",
            "description": "Get one safe joke.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "random_dog",
            "description": "Get a random dog photo URL.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "trivia",
            "description": "Get a trivia question with answer options.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    }
]


def request_json(url, params=None):
    response = requests.get(url, params=params, timeout=TIMEOUT)
    response.raise_for_status()
    data = response.json()

    if not isinstance(data, dict):
        raise ValueError("Unexpected response from external API.")

    return data


def get_weather(latitude, longitude):
    latitude = float(latitude)
    longitude = float(longitude)

    if not -90 <= latitude <= 90:
        raise ValueError("Latitude must be between -90 and 90.")

    if not -180 <= longitude <= 180:
        raise ValueError("Longitude must be between -180 and 180.")

    data = request_json(
        "https://api.open-meteo.com/v1/forecast",
        {
            "latitude": latitude,
            "longitude": longitude,
            "current": "temperature_2m,relative_humidity_2m,apparent_temperature,weather_code,wind_speed_10m",
            "timezone": "auto"
        }
    )

    return {
        "current": data.get("current", {}),
        "units": data.get("current_units", {}),
        "source": "https://open-meteo.com/"
    }


def get_weather_by_city(city):
    data = request_json(
        "https://geocoding-api.open-meteo.com/v1/search",
        {"name": city, "count": 1, "language": "en", "format": "json"}
    )

    places = data.get("results", [])

    if not places:
        return {"error": f"No location found for {city}."}

    place = places[0]

    weather = get_weather(
        place["latitude"],
        place["longitude"]
    )

    weather["location"] = ", ".join(
        str(value)
        for value in [
            place.get("name"),
            place.get("admin1"),
            place.get("country")
        ]
        if value
    )

    return weather


def book_recs(topic, limit=3):
    limit = max(1, min(int(limit), 5))

    data = request_json(
        "https://openlibrary.org/search.json",
        {"q": topic, "limit": limit}
    )

    books = []

    for item in data.get("docs", [])[:limit]:
        key = item.get("key")

        books.append({
            "title": item.get("title", "Unknown title"),
            "author": (item.get("author_name") or ["Unknown author"])[0],
            "year": item.get("first_publish_year"),
            "url": (
                "https://openlibrary.org" + key
                if key and key.startswith("/works/")
                else None
            )
        })

    return {"topic": topic, "books": books}


def random_joke():
    data = request_json(
        "https://v2.jokeapi.dev/joke/Any",
        {"type": "single", "safe-mode": ""}
    )

    if data.get("error") or not data.get("joke"):
        raise ValueError("A safe joke could not be retrieved.")

    return {"joke": data["joke"]}


def random_dog():
    data = request_json(
        "https://dog.ceo/api/breeds/image/random"
    )

    if data.get("status") != "success":
        raise ValueError("Could not retrieve a dog photo.")

    return {"image_url": data["message"]}


def trivia():
    data = request_json(
        "https://opentdb.com/api.php",
        {"amount": 1, "type": "multiple"}
    )

    results = data.get("results", [])

    if not results:
        raise ValueError("No trivia question was returned.")

    item = results[0]
    correct = html.unescape(item["correct_answer"])
    options = [
        html.unescape(value)
        for value in item.get("incorrect_answers", [])
    ]
    options.append(correct)
    random.shuffle(options)

    return {
        "category": html.unescape(item.get("category", "General")),
        "question": html.unescape(item["question"]),
        "options": options,
        "correct_answer": correct
    }


TOOL_FUNCTIONS = {
    "get_weather_by_city": get_weather_by_city,
    "get_weather": get_weather,
    "book_recs": book_recs,
    "random_joke": random_joke,
    "random_dog": random_dog,
    "trivia": trivia
}


def execute_tool(name, arguments):
    if name not in TOOL_FUNCTIONS:
        return {"ok": False, "error": f"Unknown tool: {name}"}

    if not isinstance(arguments, dict):
        return {"ok": False, "error": "Tool arguments must be an object."}

    try:
        result = TOOL_FUNCTIONS[name](**arguments)
        return {"ok": True, "data": result}
    except requests.RequestException:
        return {
            "ok": False,
            "error": f"{name} could not connect to its external API."
        }
    except (ValueError, TypeError, KeyError) as exc:
        return {"ok": False, "error": str(exc)}
    except Exception:
        return {"ok": False, "error": f"{name} failed unexpectedly."}


def run_agent(question):
    question = question.strip()

    if not question:
        raise ValueError("Please enter a question.")

    if len(question) > 8000:
        raise ValueError("Question must be 8,000 characters or fewer.")

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": question}
    ]

    tools_used = []
    observations = []

    for _ in range(MAX_STEPS):
        response = client.chat(
            model=MODEL_NAME,
            messages=messages,
            tools=TOOL_SCHEMAS,
            options={"temperature": 0.1}
        )

        message = response.message
        tool_calls = message.tool_calls or []

        if not tool_calls:
            answer = (message.content or "").strip()

            if not answer:
                answer = "I could not generate an answer."

            break

        messages.append(message)

        for call in tool_calls:
            name = call.function.name
            arguments = call.function.arguments or {}

            result = execute_tool(name, arguments)

            tools_used.append(name)
            observations.append({
                "tool": name,
                "arguments": arguments,
                "result": result
            })

            messages.append({
                "role": "tool",
                "name": name,
                "content": json.dumps(result, ensure_ascii=False)
            })
    else:
        answer = (
            message.content or
            "I reached the tool-call limit. Please try a simpler request."
        )

    try:
        review = client.chat(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": REFLECTION_PROMPT},
                {
                    "role": "user",
                    "content": json.dumps({
                        "question": question,
                        "draft_answer": answer,
                        "tool_results": observations
                    }, ensure_ascii=False)
                }
            ],
            options={"temperature": 0}
        )

        reviewed_answer = (review.message.content or "").strip()

        if reviewed_answer:
            answer = reviewed_answer

    except Exception:
        pass

    return {
        "answer": answer,
        "model": MODEL_NAME,
        "tools_used": tools_used,
        "tool_calls": observations
    }