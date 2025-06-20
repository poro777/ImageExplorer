from typing import Union
from router import vector_db_api, image_api

from fastapi import FastAPI


app = FastAPI()
app.include_router(vector_db_api.router)
app.include_router(image_api.router)


@app.get("/")
def read_root():
    return {"Good": "v8"}

