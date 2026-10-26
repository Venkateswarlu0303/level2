import logging
import os

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from archestrattor import MODEL_NAME, client, run_agent

logging.basicConfig(level=logging.INFO)

app = FastAPI(
    title="Local AI Tool-Calling Agent",
    description="Qwen 7B agent powered by Ollama and external API tools."
)


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=8000)


@app.get("/")
def home():
    return {
        "message": "Local AI Tool-Calling Agent is running.",
        "model": MODEL_NAME,
        "chat_endpoint": "POST /chat",
        "health_endpoint": "GET /health"
    }


@app.get("/health")
def health():
    return {
        "status": "ok",
        "model": MODEL_NAME,
        "ollama_host": os.getenv(
            "OLLAMA_HOST",
            "http://localhost:11434"
        )
    }


@app.get("/ready")
def ready():
    try:
        result = client.list()
        models = getattr(result, "models", []) or []

        names = [
            getattr(item, "model", None)
            or getattr(item, "name", "")
            for item in models
        ]

        installed = any(
            name == MODEL_NAME or name.startswith(MODEL_NAME + ":")
            for name in names
        )

        if not installed:
            raise HTTPException(
                status_code=503,
                detail=f"Model not installed. Run: ollama pull {MODEL_NAME}"
            )

        return {"status": "ready", "model": MODEL_NAME}

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Ollama is unavailable: {type(exc).__name__}"
        ) from exc


@app.post("/chat")
def chat_endpoint(payload: ChatRequest):
    try:
        result = run_agent(payload.question)
        return result

    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    except Exception as exc:
        logging.exception("Agent request failed")
        raise HTTPException(
            status_code=503,
            detail=(
                "The agent could not complete the request. "
                "Check that Ollama is running and the Qwen model is installed."
            )
        ) from exc