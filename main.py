from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI

from clients.http import SyncHttpClient


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    print("Startup")
    SyncHttpClient.configure(base_url="https://httpbin.org")
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


@app.get("/sync/local/context-manager")
async def sync_local_context_manager_usecase() -> list[dict]:
    # Context manager automatically opens and closes a local httpx client.
    with SyncHttpClient(base_url="https://jsonplaceholder.typicode.com") as client:
        response = client.get("/todos", params={"_limit": 5})

    return response.json()


if __name__ == "__main__":
    uvicorn.run("main:app", reload=True)
