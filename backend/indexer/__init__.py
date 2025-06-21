from indexer.vector_db import query, delete_one, insert_one, list_data, COLLECTION_NAME, create_embed_db
from indexer.vector_db import insert_image, query_images_by_text
from indexer import genai_api

genai_api.init()