import asyncio

from fastapi import APIRouter

from clients.http import AsyncHttpClient, HttpClient, HttpRetryStrategy
from retry import RetryStrategy

router = APIRouter(prefix="/http")


@router.get("/global")
async def global_usecase() -> dict:
    client = HttpClient()

    # By default client uses the global httpx client.
    response = client.get("/get")

    return response.json()


@router.get("/local")
async def local_usecase() -> dict:
    client = HttpClient()

    # It opens a local httpx client, instead of using the global one.
    client.open()
    response = client.get("/get")
    client.close()

    return response.json()


@router.get("/local/async")
async def local_async_usecase() -> list[dict]:
    client = AsyncHttpClient()

    # In case you forgot to open the client, it will be opened automatically.
    responses = await asyncio.gather(
        client.get("https://httpbin.org/get"),
        client.get("https://httpbin.org/get"),
        client.get("https://httpbin.org/get"),
    )
    await client.close()

    return [response.json() for response in responses]


@router.get("/local/context-manager")
async def local_context_manager_usecase() -> list[dict]:
    # Context manager automatically opens and closes a local httpx client.
    with HttpClient(base_url="https://jsonplaceholder.typicode.com") as client:
        response = client.get("/todos", params={"_limit": 5})

    return response.json()


@router.get("/local/timeout")
async def local_timeout_usecase() -> list[dict]:
    # Local client timeout takes precedence over the global timeout.
    client = HttpClient(timeout=5)

    client.open()
    # Concreate request timeout has the highest priority.
    response = client.get("http://127.0.0.1:5000/users", timeout=2)
    client.close()

    return response.json()


@router.get("/local/retry")
async def local_retry_usecase() -> list[dict]:
    with HttpClient(
        base_url="http://127.0.0.1:5000",
        timeout=5,
        # In this case requests will to be retried in case of any exception, including timeouts.
        retry_strategy=RetryStrategy(attempts=3, delay=1),
    ) as client:
        response = client.get("/posts")

    return response.json()


@router.get("/local/error")
async def local_error_usecase() -> dict:
    with HttpClient(
        base_url="http://127.0.0.1:5000",
        retry_strategy=HttpRetryStrategy(attempts=3, delay=1, on_statuses={"server_error"}),
    ) as client:
        response = client.get("/server-error")

    return response.json()
