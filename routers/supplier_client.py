from fastapi import APIRouter

from clients.http import SyncSupplierClient

router = APIRouter(prefix="/supplier")


@router.get("/global")
async def global_usecase() -> dict:
    client = SyncSupplierClient()

    response = client.get("/get", name="GLOBAL")

    return response.json()


@router.get("/local")
async def local_usecase() -> dict:
    client = SyncSupplierClient()

    client.open()
    response = client.get("/get", name="LOCAL")
    client.close()

    return response.json()


@router.get("/local/custom_supplier_code")
async def local_custom_supplier_code_usecase(supplier_code: str) -> dict:
    client = SyncSupplierClient()

    client.open()
    response = client.get("/get", name="LOCAL_CUSTOM_SUPPLIER_CODE", supplier_code=supplier_code)
    client.close()

    return response.json()
