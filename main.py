from __future__ import annotations

import logging
import logging.config
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

import uvicorn
from fastapi import FastAPI

from clients.broker import SQSClient
from clients.http import (
    SQSSupplierMessageBuilder,
    SupplierRequestLogConfig,
    SupplierResponseLogConfig,
    SyncHttpClient,
    SyncSupplierClient,
)
from routers import http_client_router, supplier_client_router

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator


logging.config.dictConfig(
    {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "format": "%(levelname)s %(asctime)s %(message)s",
            },
            "json": {
                "format": "%(levelname)s %(asctime)s %(message)s",
                "()": "pythonjsonlogger.jsonlogger.JsonFormatter",
                "json_indent": 4,
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
                "level": "INFO",
                "handlers": ["console"],
            },
            "utils.clients.broker": {
                "level": "INFO",
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

    SyncSupplierClient.configure(
        supplier_code="RCL",
        base_url="https://httpbin.org",
        request_log_config=SupplierRequestLogConfig(
            request_headers=True,
            request_body=True,
        ),
        response_log_config=SupplierResponseLogConfig(
            response_headers=True,
            response_body=True,
        ),
        broker_client=SQSClient(
            queue_url="http://sqs.eu-north-1.localhost.localstack.cloud:4566/000000000000/UtilsQueue",
            region_name="eu-north-1",
            log_attributes=True,
            log_body=True,
            singleton=True,
        ),
        broker_message_builder=SQSSupplierMessageBuilder(
            allowed_request_names={"LOCAL"},
            disallowed_request_tags={None},
        ),
    )
    SyncSupplierClient.open_global()

    yield

    SyncHttpClient.close_global()
    SyncSupplierClient.close_global()

    print("Shutdown")


app = FastAPI(lifespan=lifespan)

app.include_router(http_client_router)
app.include_router(supplier_client_router)


if __name__ == "__main__":
    uvicorn.run("main:app", port=8000, reload=True)
