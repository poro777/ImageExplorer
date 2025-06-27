from indexer.vector_db import is_collection_exist, create_embed_db, COLLECTION_NAME
from indexer.vector_db import delete_one, list_data, delete_by_list
from indexer.vector_db import insert_image, query_images_by_text, change_partition

from indexer.vector_db import FIELD_ID, FIELD_TEXT

from indexer import genai_api

genai_api.init()