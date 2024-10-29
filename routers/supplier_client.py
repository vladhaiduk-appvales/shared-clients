import asyncio

from fastapi import APIRouter

from clients.broker import AsyncSQSClient
from clients.http import AsyncHttpRetryStrategy, AsyncSupplierClient, SQSSupplierMessageBuilder, SupplierClient

router = APIRouter(prefix="/supplier")


@router.get("/global")
async def global_usecase() -> dict:
    client = SupplierClient()

    response = client.get("/get")

    return response.json()


@router.get("/local")
async def local_usecase() -> dict:
    client = SupplierClient()

    client.open()
    response = client.get("/get", name="LOCAL")
    client.close()

    return response.json()


@router.get("/local/async")
async def local_async_usecase() -> list[dict]:
    sqs_client = AsyncSQSClient(
        queue_url="http://sqs.eu-north-1.localhost.localstack.cloud:4566/000000000000/UtilsQueue",
        region_name="eu-north-1",
        log_attributes=True,
        log_body=True,
    )
    await sqs_client.connect()

    async with AsyncSupplierClient(
        base_url="https://httpbin.org",
        retry_strategy=AsyncHttpRetryStrategy(attempts=3, delay=1),
        broker_client=sqs_client,
        broker_message_builder=SQSSupplierMessageBuilder(allowed_request_names={"LOCAL"}),
    ) as client:
        responses = await asyncio.gather(
            client.get("/get", name="LOCAL", tag="ASYNC"),
            client.get("/get", name="LOCAL", tag="ASYNC"),
            client.get("/get", name="LOCAL", tag="ASYNC"),
        )

    await sqs_client.disconnect()

    return [response.json() for response in responses]


@router.get("/local/custom_supplier_code")
async def local_custom_supplier_code_usecase(supplier_code: str) -> dict:
    client = SupplierClient()

    client.open()
    response = client.get("/get", name="LOCAL", tag="CSC", supplier_code=supplier_code)
    client.close()

    return response.json()
