# watcher.py
import os
import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from pathlib import Path
import threading

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


class ImageChangeHandler(FileSystemEventHandler):
    def on_created(self, event):
        # WAITING FOR FILE TRANSFER
        while is_file_ready(event.src_path) == False:
            pass
        
        print(f"[watchdog] File created: {event.src_path}")

    def on_deleted(self, event):
        print(f"[watchdog] File deleted: {event.src_path}")

    def on_modified(self, event):
        try:
            with open(event.src_path, "r") as f:
                pass
        except:
            return
        print(f"[watchdog] File modified: {event.src_path}")

    def on_moved(self, event):
        print(f"[watchdog] File moved: {event.src_path}")


class WatchdogService:
    def __init__(self, path: str):
        self.path = Path(path)
        self.observer = Observer()
        self.handler = ImageChangeHandler()
        self.thread = threading.Thread(target=self.run, daemon=True)

    def run(self):
        self.observer.schedule(self.handler, str(self.path), recursive=False)
        self.observer.start()
        self.observer.join()  # blocking

    def start(self):
        print(f"[watchdog] Watching {self.path}")
        self.thread.start()

    def stop(self):
        print(f"[watchdog] Stopping...")
        self.observer.stop()
        self.observer.join()
