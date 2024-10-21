import logging
import logging.config
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI

from clients.http import SyncHttpClient
from retry import RetryStrategy

logging.config.dictConfig(
    {
        "version": 1,
        "formatters": {
            "default": {
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "default",
            },
        },
        "loggers": {
            "utils.clients.http": {
                "level": "DEBUG",
                "handlers": ["console"],
            },
        },
    }
)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    print("Startup")
    SyncHttpClient.configure(base_url="https://httpbin.org", timeout=None)
    SyncHttpClient.open_global()
    yield
    SyncHttpClient.close_global()
    print("Shutdown")


app = FastAPI(lifespan=lifespan)


@app.get("/sync/global")
async def sync_global_usecase() -> dict:
    client = SyncHttpClient()

    # By default client uses the global httpx client.
    response = client.get("/get")

    return response.json()


@app.get("/sync/local")
async def sync_local_usecase() -> dict:
    client = SyncHttpClient()

    # It opens a local httpx client, instead of using the global one.
    client.open()
    response = client.get("/get")
    client.close()

    return response.json()


@app.get("/sync/local/timeout")
async def sync_local_timeout_usecase() -> list[dict]:
    # Local client timeout takes precedence over the global timeout.
    client = SyncHttpClient(timeout=5)

    client.open()
    # Concreate request timeout has the highest priority.
    response = client.get("http://127.0.0.1:5000/users", timeout=2)
    client.close()

    return response.json()


@app.get("/sync/local/context-manager")
async def sync_local_context_manager_usecase() -> list[dict]:
    # Context manager automatically opens and closes a local httpx client.
    with SyncHttpClient(base_url="https://jsonplaceholder.typicode.com") as client:
        response = client.get("/todos", params={"_limit": 5})

    return response.json()


@app.get("/sync/local/retry")
async def sync_local_retry_usecase() -> list[dict]:
    with SyncHttpClient(
        base_url="http://127.0.0.1:5000",
        timeout=5,
        # In this case requests will to be retried in case of any exception, including timeouts.
        retry_strategy=RetryStrategy(attempts=3, delay=1),
    ) as client:
        response = client.get("/posts")

    return response.json()


if __name__ == "__main__":
    uvicorn.run("main:app", port=8000, reload=True)
