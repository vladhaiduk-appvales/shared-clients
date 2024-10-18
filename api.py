import asyncio
import secrets

import uvicorn
from fastapi import FastAPI

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


if __name__ == "__main__":
    uvicorn.run("api:app", port=5000, reload=True)
