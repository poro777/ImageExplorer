import os

from PIL import Image
from io import BytesIO

import indexer
from pathlib import Path

from fastapi import APIRouter

router = APIRouter(
    prefix="/api",
    tags=["vector_db"],
)


@router.get('/query')
def query_text(text: str, use_text_embed: bool, use_bm25: bool, use_joint_embed: bool):

    clip_text_features = indexer.get_text_embed(text)
    text_features = indexer.get_text_embed_query(text)
    use_image_embed = False
    clip_image_features = None
    top_k = 10
    results = indexer.query_one(indexer.COLLECTION_NAME, top_k, text, text_features, clip_text_features, clip_image_features, 
                                use_text_embed, use_bm25, use_joint_embed, use_image_embed )

    #TODO

    return results

@router.get('/list')
def query_all():
    results = indexer.list_data(indexer.COLLECTION_NAME)
    
    #TODO

    return results