from io import BytesIO
import json
import os
import pathlib
from google import genai
import threading
import time
import re
from dotenv import load_dotenv

load_dotenv()
genai_api_key = os.getenv("GENAI_API_KEY")

if genai_api_key is None:
    raise Exception("GENAI_API_KEY is not set, please set it in .env file or environment variable")


prompt_string = "Caption this image."
CACHE_TEXT = {}

last_explanation_time = 0
COOLDOWN_PERIOD = 10  # seconds
explain_image_lock = threading.Lock()

def init():
    '''load cache text and prompt string'''
    global CACHE_TEXT, prompt_string
    file_root = pathlib.Path(__file__).parent.resolve()

    try:
        with open(file_root / "data.json", "r") as f:
            CACHE_TEXT = json.load(f)
    except Exception as e:
        print("Error", e)
        CACHE_TEXT = {}

    try:
        with open(file_root / "genai_prompt.txt", "r", encoding="utf-8") as f:
            prompt_string = f.read()
    except Exception as e:
        print(e)
        prompt_string = "Caption this image."
    
def store_cache():
    global CACHE_TEXT
    file_root = pathlib.Path(__file__).parent.resolve()

    try:
        with open(file_root / "data.json", "w") as f:
            json.dump(CACHE_TEXT, f, indent=4)  # optional: indent for readability
    except:
        pass

    
def sanitize_string(s):
    s = s.lower()
    s = re.sub(r'[^a-z0-9\-]', '-', s)
    return s

def explainImage(id:str, image_format, image_data: BytesIO, use_cache: bool = True):
    global last_explanation_time, explain_image_lock, prompt_string, COOLDOWN_PERIOD, CACHE_TEXT

    if use_cache and (id in CACHE_TEXT):
        return CACHE_TEXT[id]
        
    client = genai.Client(api_key=genai_api_key)

    file_id = sanitize_string(id)
    file_id = file_id[-40:] # limit to 40 char
    if file_id[0] == "-":
        file_id = file_id.replace("-", "a", 1)


    try:
        print(f"[GET file] {file_id}")
        my_file = client.files.get(name=file_id)
    except Exception as e:
        print("Load error: ", e)
        my_file = None
    
    with explain_image_lock:
        current_time = time.time()
        time_since_last_call = current_time - last_explanation_time
        
        if time_since_last_call < COOLDOWN_PERIOD:
            sleep_duration = COOLDOWN_PERIOD - time_since_last_call
            print(f"Cooldown active. Thread will sleep for {sleep_duration:.1f} seconds.")
            time.sleep(sleep_duration)
        
        try:
            if my_file is None:
                # Ensure image_data is at the beginning if it was read before
                image_data.seek(0)
                my_file = client.files.upload(file=image_data, config={
                    "mime_type": f'image/{image_format}',
                    "name": file_id
                })


            response = client.models.generate_content(
                model="gemini-2.0-flash", # Consider making the model name a configurable parameter
                contents=[my_file, prompt_string],
            )
            last_explanation_time = time.time() # Update last execution time only on success
        except Exception as e:
            print("Gen error: ", e)
            return "" # Or raise the exception, or return a more specific error message

    response = response.text if response.text is not None else ""

    if use_cache:
        CACHE_TEXT[id] = response
        store_cache()
    return response


def list_uploaded_files():
    client = genai.Client(api_key=genai_api_key)
    print('My files:')
    for f in client.files.list():
        print(f.name)

def delete_uploaded_files():
    client = genai.Client(api_key=genai_api_key)
    print(f'Delete: {len(client.files.list())}')
    for f in client.files.list():
        client.files.delete(name=f.name)


if __name__ == "__main__":
    list_uploaded_files()
    pass