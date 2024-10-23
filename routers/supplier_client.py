from fastapi import APIRouter

from clients.http import SyncSupplierClient

router = APIRouter(prefix="/supplier")


@router.get("/global")
async def sync_supplier_global_usecase() -> dict:
    client = SyncSupplierClient()

    response = client.get("/get")

    return response.json()


@router.get("/local")
async def sync_supplier_local_usecase() -> dict:
    client = SyncSupplierClient()

    client.open()
    response = client.get("/get")
    client.close()

    return response.json()


@router.get("/local/custom_supplier_code")
async def sync_supplier_local__usecase(supplier_code: str) -> dict:
    client = SyncSupplierClient()

    client.open()
    response = client.get("/get", supplier_code=supplier_code)
    client.close()

    return response.json()
