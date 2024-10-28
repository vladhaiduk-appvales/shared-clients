import asyncio
import secrets

import uvicorn
from fastapi import FastAPI
from fastapi.responses import JSONResponse

app = FastAPI()


@app.get("/users")
async def read_users() -> list[dict]:
    await asyncio.sleep(10)
    return [
        {"username": "Rick"},
        {"username": "Morty"},
        {"username": "Summer"},
        {"username": "Beth"},
        {"username": "Jerry"},
    ]


@app.get("/posts")
async def read_posts() -> list[dict]:
    rand = secrets.randbelow(5) + 1  # From 1 to 5
    await asyncio.sleep(rand * 2)
    return [
        {"title": "Understanding Asyncio in Python"},
        {"title": "FastAPI vs Flask: A Comparison"},
        {"title": "Building a REST API with FastAPI"},
        {"title": "Introduction to Python Generators"},
        {"title": "Mastering Python Decorators"},
    ]


@app.get("/redirect")
async def read_redirect() -> JSONResponse:
    return JSONResponse(status_code=300, content={"redirect": "Redirecting"})


@app.get("/client-error")
async def read_client_error() -> JSONResponse:
    return JSONResponse(status_code=400, content={"error": "Client Error"})


@app.get("/server-error")
async def read_server_error() -> JSONResponse:
    return JSONResponse(status_code=500, content={"error": "Server Error"})


if __name__ == "__main__":
    uvicorn.run("api:app", port=5000, reload=True)
