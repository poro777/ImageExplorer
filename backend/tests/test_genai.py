from tests.utils import *
from tests.constants import *

from PIL import Image as ImageLoader
from PIL.ImageFile import ImageFile

import indexer

def test_genai_api():
    from io import BytesIO

    id1 = "test-image"
    image: ImageFile = ImageLoader.open(BASE_DIR / PATH_FLOWER_IMAGE)
    image_format = image.format.lower()

    # Convert to BytesIO
    buffer = BytesIO()
    image.save(buffer, format=image_format) 
    buffer.seek(0)  # rewind to the start of the stream

    firstRequestTime = time.time()
    text = indexer.genai_api.explainImage(id1, image_format, buffer, use_cache=False)

    assert text is not None
    assert len(text) > 0
    assert any((keywork in text) for keywork in ["flower", "floral", "baby's breath"])

    id2 = "_test-image"
    image: ImageFile = ImageLoader.open(BASE_DIR / PATH_HUSKY_IMAGE)
    image_format = image.format.lower()

    buffer = BytesIO()
    image.save(buffer, format=image_format) 
    buffer.seek(0) 

    text = indexer.genai_api.explainImage(id2, image_format, buffer, use_cache=False)
    secondResponseTime = time.time()

    assert text is not None
    assert len(text) > 0
    assert any((keywork in text) for keywork in ["husky", "dog", "snow"])

    assert secondResponseTime - firstRequestTime > indexer.genai_api.COOLDOWN_PERIOD


    indexer.genai_api.delete_uploaded_file(id1)
    indexer.genai_api.delete_uploaded_file(id2)

