from indexer.vector_db import query_one, delete_one, insert_one, list_data, COLLECTION_NAME
from indexer.genai_api import explainImage
from indexer.text_embed import get_text_embed_doc, get_text_embed_query
from indexer.clip_embed import get_image_embed, get_text_embed

from indexer import vector_db
from indexer import genai_api

if vector_db.is_collection_exist(COLLECTION_NAME) == False:
    vector_db.create_embed_db(COLLECTION_NAME)


genai_api.init()