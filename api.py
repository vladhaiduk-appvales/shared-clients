import asyncio

import uvicorn
from fastapi import FastAPI

app = FastAPI()


@app.get("/users")
async def read_users() -> list[dict]:
    await asyncio.sleep(10)
    return [{"username": "Rick"}, {"username": "Morty"}]


if __name__ == "__main__":
    uvicorn.run("api:app", port=5000, reload=True)
