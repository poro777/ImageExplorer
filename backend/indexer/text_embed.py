import threading
from pymilvus import model

model2vec_ef = None
model_lock = threading.Lock()

def getModel():
    global model2vec_ef
    if model2vec_ef is None:
        with model_lock:
            model2vec_ef = model.dense.Model2VecEmbeddingFunction(
                model_source='minishlab/potion-base-8M', # or local directory
            )

    return model2vec_ef

def get_text_embed_doc(text):
    model2vec_ef = getModel()
    docs_embeddings = model2vec_ef.encode_documents([text])
    return docs_embeddings[0]

def get_text_embed_query(text):
    model2vec_ef = getModel()
    docs_embeddings = model2vec_ef.encode_queries([text])
    return docs_embeddings[0]