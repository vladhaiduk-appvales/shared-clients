from __future__ import annotations

import logging
import logging.config
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

import uvicorn
from fastapi import FastAPI

from clients.broker import SQSClient, SQSMessageBuilder
from clients.http import (
    BrokerHttpMessageBuilder,
    Request,
    Response,
    SupplierRequestLogConfig,
    SupplierResponseLogConfig,
    SyncHttpClient,
    SyncSupplierClient,
)
from routers import http_client_router, supplier_client_router

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
            "utils.clients.broker": {
                "level": "INFO",
                "handlers": ["console"],
            },
        },
    }
)


class SupplierSQSMessageBuilder(BrokerHttpMessageBuilder, SQSMessageBuilder):
    def build_metadata(
        self, _request: Request, _response: Response, details: DetailsType | None = None
    ) -> dict[str, any] | None:
        supplier_code = details.get("supplier_code")
        return {
            "SupplierCode": self.string_attr(supplier_code),
        }

    def build_body(self, _request: Request, _response: Response, details: DetailsType | None = None) -> str:
        supplier_code = details.get("supplier_code")
        return f"Hello from {supplier_code} :D"


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
            singleton=True,
        ),
        broker_message_builder=SupplierSQSMessageBuilder(),
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
