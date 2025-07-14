from router import vector_db_api, file_api, sqlite_api, watcher_api
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends
from sqlmodel import Session, select
from database import models

from database import database
import indexer
import watcher

@asynccontextmanager
async def lifespan(app: FastAPI):
    database.init_db()

    if indexer.is_collection_exist(indexer.COLLECTION_NAME) == False:
        indexer.create_embed_db(indexer.COLLECTION_NAME)

    watcher.fs_watcher.start()

    yield

    watcher.fs_watcher.stop()

app = FastAPI(lifespan=lifespan)

app.include_router(vector_db_api.router)
app.include_router(file_api.router)
app.include_router(sqlite_api.router)
app.include_router(watcher_api.router)

@app.get("/")
def read_root():
    return {"Good": "v8"}

