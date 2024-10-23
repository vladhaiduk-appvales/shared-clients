from __future__ import annotations

import logging
import logging.config
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

import uvicorn
from fastapi import FastAPI

from clients.broker import BrokerClient, BrokerMessage
from clients.http import (
    BrokerHttpMessageBuilder,
    Request,
    Response,
    SupplierRequestLogConfig,
    SupplierResponseLogConfig,
    SyncHttpClient,
    SyncSupplierClient,
)
from retry import RetryStrategy

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from clients.http.types_ import DetailsType

logging.config.dictConfig(
    {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "json": {
                "format": "%(levelname)s %(asctime)s %(message)s",
                "()": "pythonjsonlogger.jsonlogger.JsonFormatter",
                "json_indent": 4,
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "json",
            },
        },
        "loggers": {
            "utils.clients.http": {
                "level": "INFO",
                "handlers": ["console"],
            },
        },
    }
)


class DumbBrokerClient(BrokerClient):
    def send_message(self, message: BrokerMessage) -> None:
        print("+++ DumbBrokerClient +++")
        print(message)


class DumbBrokerMessageBuilder(BrokerHttpMessageBuilder):
    def build_metadata(
        self, _request: Request, _response: Response, details: DetailsType | None = None
    ) -> dict[str, any] | None:
        return {"request_name": details.get("request_name")}

    def build_body(self, _request: Request, _response: Response, details: DetailsType | None = None) -> any | None:
        return details.get("request_name")


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    print("Startup")

    SyncHttpClient.configure(
        base_url="https://httpbin.org",
        timeout=None,
        broker_client=DumbBrokerClient("xxx"),
        broker_message_builder=DumbBrokerMessageBuilder(),
    )
    SyncHttpClient.open_global()

    SyncSupplierClient.configure(
        supplier_code="RCL",
        base_url="https://httpbin.org",
        request_log_config=SupplierRequestLogConfig(request_headers=True, request_body=True),
        response_log_config=SupplierResponseLogConfig(response_headers=True, response_body=True),
    )
    SyncSupplierClient.open_global()

    yield

    SyncHttpClient.close_global()
    SyncSupplierClient.close_global()

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


@app.get("/sync_supplier/global")
async def sync_supplier_global_usecase() -> dict:
    client = SyncSupplierClient()

    response = client.get("/get")

    return response.json()


@app.get("/sync_supplier/local")
async def sync_supplier_local_usecase() -> dict:
    client = SyncSupplierClient()

    client.open()
    response = client.get("/get")
    client.close()

    return response.json()


@app.get("/sync_supplier/local/custom_supplier_code")
async def sync_supplier_local__usecase(supplier_code: str) -> dict:
    client = SyncSupplierClient()

    client.open()
    response = client.get("/get", supplier_code=supplier_code)
    client.close()

    return response.json()


if __name__ == "__main__":
    uvicorn.run("main:app", port=8000, reload=True)
