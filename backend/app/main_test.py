from fastapi import FastAPI
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("LIFESPAN: STARTING")
    yield
    print("LIFESPAN: STOPPING")

app = FastAPI(lifespan=lifespan)

@app.get("/")
async def root():
    return {"message": "hello"}
