from router import vector_db_api, file_api, sqlite_api, watcher_api
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends
from sqlmodel import Session, select
from database import models

from database import database
from indexer import vector_db

from watcher import *
watcher = WatchdogService(path="./images")  # can load from config/env


@asynccontextmanager
async def lifespan(app: FastAPI):
    database.init_db()
    if vector_db.is_collection_exist(vector_db.COLLECTION_NAME) == False:
        vector_db.create_embed_db(vector_db.COLLECTION_NAME)
    watcher.start()
    yield
    watcher.stop()

app = FastAPI(lifespan=lifespan)

app.include_router(vector_db_api.router)
app.include_router(file_api.router)
app.include_router(sqlite_api.router)
app.include_router(watcher_api.router)

@app.get("/")
def read_root():
    return {"Good": "v8"}

