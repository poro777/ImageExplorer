import os
from typing import Optional

from PIL import Image
from io import BytesIO

import indexer
from pathlib import Path

from fastapi import APIRouter, HTTPException
from sqlmodel import Session
from database.database import engine
from router.file_api import getFolder
from database.utils import get_directory_id

router = APIRouter(
    prefix="/api",
    tags=["vector_db"],
)


@router.get('/query')
def query_text(text: str, use_text_embed: bool, use_bm25: bool, use_joint_embed: bool, path: Optional[str] = None):

    top_k = 10

    path = getFolder(path)
    partition_id = get_directory_id(path.as_posix()) if path is not None else None
    
    if partition_id is None and path is not None:
        # given path is not found
        raise HTTPException(status_code=404, detail="Path is not in database")
    
    results = indexer.query_images_by_text(top_k, text, use_text_embed, use_bm25, use_joint_embed, partition_id )

    #TODO

    return results

@router.get('/list')
def query_all(path: Optional[str] = None):

    path = getFolder(path)
    partition_id = get_directory_id(path.as_posix()) if path is not None else None
    
    if partition_id is None and path is not None:
        # given path is not found
        raise HTTPException(status_code=404, detail="Path is not in database")
    
    partitions = [str(partition_id)] if partition_id is not None else None
    results = indexer.list_data(indexer.COLLECTION_NAME, partitions)
    
    #TODO

    return results