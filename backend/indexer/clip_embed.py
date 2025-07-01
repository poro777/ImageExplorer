import threading
import torch
from PIL import Image
import open_clip
import numpy as np

def to_np(arr: torch.Tensor) -> np.ndarray:
    return arr.detach().cpu().numpy()

model = None
preprocess = None
tokenizer = None
device = "cuda" if torch.cuda.is_available() else "cpu"
model_lock = threading.Lock()

def getModel():
    global model, preprocess, tokenizer
    if model is None:
        with model_lock:
            if model is None:
                print("Loading model : ", device)
                model, _, preprocess = open_clip.create_model_and_transforms('ViT-B-32', pretrained='laion2b_s34b_b79k')
                model.eval().to(device)  # model in train mode by default, impacts some models with BatchNorm or stochastic depth active
                tokenizer = open_clip.get_tokenizer('ViT-B-32')
    return model, preprocess, tokenizer


def get_image_embed(image):
    model, preprocess, _ = getModel()
    image_proc = preprocess(image).unsqueeze(0).to(device)
    image_features = model.encode_image(image_proc)

    return to_np(image_features[0]).tolist()

def get_text_embed(text):
    model, _, tokenizer = getModel()
    
    text_tok = tokenizer([text]).to(device)
    text_features = model.encode_text(text_tok)

    return to_np(text_features[0]).tolist()
