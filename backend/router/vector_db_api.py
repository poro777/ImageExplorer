from typing import Optional
import indexer

from fastapi import APIRouter, HTTPException
import indexer.vector_db
from router.file_api import getFolderPath
from database.utils import get_directory_id, query_images_by_id_list
from database.models import Image


router = APIRouter(
    prefix="/api",
    tags=["vector_db"],
)


@router.get('/query')
def query_text(text: str, use_text_embed: bool, use_bm25: bool, use_joint_embed: bool, path: Optional[str] = None):

    top_k = 10

    path = getFolderPath(path)
    partition_id = get_directory_id(path.as_posix()) if path is not None else None
    
    if partition_id is None and path is not None:
        # given path is not found
        raise HTTPException(status_code=404, detail="Path is not in database")
    
    results = indexer.query_images_by_text(indexer.COLLECTION_NAME, top_k, text, use_text_embed, use_bm25, use_joint_embed, partition_id )
    images = query_images_by_id_list([result[indexer.vector_db.FIELD_ID] for result in results])

    distances = {result[indexer.vector_db.FIELD_ID]: result["distance"] for result in results}
    
    def convert(image: Image):
        result = dict(image)
        result['distance'] = distances[image.id]
        return result
    
    return sorted(map(convert, images), key=lambda x: x['distance'], reverse=True)

@router.get('/list')
def query_all(path: Optional[str] = None):

    path = getFolderPath(path)
    partition_id = get_directory_id(path.as_posix()) if path is not None else None
    
    if partition_id is None and path is not None:
        # given path is not found
        raise HTTPException(status_code=404, detail="Path is not in database")
    
    partitions = [str(partition_id)] if partition_id is not None else None
    results = indexer.list_data(indexer.COLLECTION_NAME, partitions)

    return results

@router.get('/text')
def query_by_id(id: int):
    results = indexer.get_images_by_ids(indexer.COLLECTION_NAME, [id])
    if len(results) == 0:
        raise HTTPException(status_code=404, detail="Image not found")
    return results