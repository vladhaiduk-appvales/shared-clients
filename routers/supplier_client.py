from fastapi import APIRouter

from clients.http import SupplierClient

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


@router.get("/local/custom_supplier_code")
async def local_custom_supplier_code_usecase(supplier_code: str) -> dict:
    client = SupplierClient()

    client.open()
    response = client.get("/get", name="LOCAL", tag="CSC", supplier_code=supplier_code)
    client.close()

    return response.json()
