# watcher.py
import os
import time
from sqlmodel import Session
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from pathlib import Path
import threading

from database.database import engine

from router.file_api import getPathOfImageFile, ALLOWED_EXTENSIONS
from router.sqlite_api import inesrt_or_update_image, delete_image
from database.utils import move_image_path

def is_file_ready(path, timeout=2):
    """Wait until file size is stable (not changing)."""
    prev_size = -1
    for _ in range(timeout * 10):  # check every 0.1s
        try:
            curr_size = os.path.getsize(path)
            if curr_size == prev_size:
                return True
            prev_size = curr_size
        except FileNotFoundError:
            pass
        time.sleep(0.1)
    return False

def is_image(file: Path):
    return file.suffix.lower() in ALLOWED_EXTENSIONS



class ImageChangeHandler(FileSystemEventHandler):
    def __init__(self):
        super().__init__()
        # store the original file path
        self.on_moved_name = {}

    def on_created(self, event):
        if not is_image(Path(event.src_path)):
            return
        
        # WAITING FOR FILE TRANSFER
        while is_file_ready(event.src_path) == False:
            pass
        
        print(f"[watchdog] Detected file created: {event.src_path}")

        with Session(engine) as session:
            try:
                if inesrt_or_update_image(event.src_path, session) is not None:
                    print(f"[watchdog] Create image: {event.src_path}")
            except Exception as e:
                print(f'[watchdog] Error insertion: {e}')
        time.sleep(0.5)


    def on_deleted(self, event):
        if not is_image(Path(event.src_path)):
            return
        
        
        file = Path(event.src_path).resolve()
 
        print(f"[watchdog] Detected file deleted: {event.src_path}")
        if delete_image(file):
            print(f"[watchdog] File deleted: {event.src_path}")
        else:
            print(f"[watchdog] Error deleting file: {event.src_path}")


    def on_modified(self, event):
        if not is_image(Path(event.src_path)):
            return
        print("[watchdog] Detected file modified:", event.src_path)
    
        try:
            with open(event.src_path, "r") as f:
                pass
        except:
            return
        
        
        if event.src_path in self.on_moved_name:
            current_path =self.on_moved_name.pop(event.src_path)
            dest_path = event.src_path
            if move_image_path(Path(current_path), Path(dest_path)):
                print(f"[watchdog] File moved: {event.src_path}")
            else:
                print(f"[watchdog] Error moving file: {event.src_path}")
        else:
            with Session(engine) as session:
                try:
                    if inesrt_or_update_image(event.src_path, session) is not None:
                        print(f"[watchdog] Create/Update image: {event.src_path}")
                except Exception as e:
                    print(f'[watchdog] Error insertion: {e}')

    def on_moved(self, event):
        if not is_image(Path(event.src_path)):
            return
        print(f"[watchdog] Detected file moved: {event.src_path} -> {event.dest_path}")
        self.on_moved_name[event.dest_path] = event.src_path

class WatchdogService:
    def __init__(self, path: str):
        self.path = Path(path).resolve()
        self.observer = Observer()
        self.handler = ImageChangeHandler()

    def start(self):
        print(f"[watchdog] Watching {self.path}")
        self.observer.schedule(self.handler, str(self.path), recursive=False)
        self.observer.start()

    def stop(self):
        print(f"[watchdog] Stopping...")
        self.observer.stop()
        self.observer.join()
