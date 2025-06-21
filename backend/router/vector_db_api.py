import os
from typing import Optional

from io import BytesIO

import indexer
from pathlib import Path

from fastapi import APIRouter, HTTPException
from sqlmodel import Session
from database.database import engine
import indexer.vector_db
from router.file_api import getFolder
from database.utils import get_directory_id, query_images_by_id_list
from database.models import Image, Directory


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
    images = query_images_by_id_list([result[indexer.vector_db.FIELD_ID] for result in results])

    distances = {result[indexer.vector_db.FIELD_ID]: result["distance"] for result in results}
    
    def convert(image: dict):
        image['distance'] = distances[image['id']]
        return image
    
    return sorted(map(convert, images), key=lambda x: x['distance'], reverse=True)

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