# watcher.py
from datetime import datetime
import os
import time
from sqlmodel import Session
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from pathlib import Path
import threading

from database.database import engine

from router.file_api import getPathOfImageFile, getFolderPath, ALLOWED_EXTENSIONS
from router.sqlite_api import inesrt_or_update_image, delete_image
from database.utils import move_image_path, get_all_listening_paths, query_images_by_path

DELAY_TIME = 0.2

dict_lock = threading.Lock()

deleted_files = dict()
created_files = dict()
moved_files = dict()
modified_files = dict()
may_moved_files = dict()

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

def only_update_metadata(file: Path):
    image = query_images_by_path(file)
    mtime = file.stat().st_mtime

    if image is None:
        return False
    
    if image.last_modified is None:
        return False
    
    return datetime.fromtimestamp(mtime) == image.last_modified
        

def create(path: str, mtime: float):
    with dict_lock:
        cmtime = created_files.get(path, None)
    on_creating = cmtime is not None

    
    if not on_creating:
        # file is already processed
        # Move: [create -> delete]
        print("[watchdog] create ignore", path)
        return
    
    with Session(engine) as session:
        try:
            if inesrt_or_update_image(path, session) is not None:
                print(f"[watchdog] Create image: {path}")
            else:
                print(f"[watchdog] Error creating image: {path}")
        except Exception as e:
            print(f'[watchdog] Error during creation: {e}')

    with dict_lock:
        _ = created_files.pop(path)
        _ = may_moved_files.pop(path, None)


def move(path: str, mtime: float):
    file  = Path(path)
    with dict_lock:
        previous_path = moved_files.get(path, None)

    if previous_path is None:
        print("[watchdog] move error: no previous_path", path)
        return
    
    if move_image_path(Path(previous_path), file, True):
        print(f"[watchdog] Move image: {previous_path} -> {path}")
    else:
        print(f"[watchdog] Error moving image: {previous_path} -> {path}")

    with dict_lock:
        _ = moved_files.pop(path)
    
    
def update(path: str, mtime: float):
    file  = Path(path)
    with dict_lock:
        modify = modified_files.get(path, None) is not None

    if modify == False:
        print("[watchdog] modify error", path)
        return
    
    with Session(engine) as session:
        try:
            if inesrt_or_update_image(path, session) is not None:
                print(f"[watchdog] Update image: {path}")
        except Exception as e:
            print(f'[watchdog] Error to update: {e}')
    with dict_lock:
        _ = modified_files.pop(path)

def delete(path: str, mtime: float):
    file  = Path(path)
    with dict_lock:
        _, mtime = deleted_files.get(file.name, (None, None))

    if mtime is None:
        # file is already processed
        # Move: [delete -> create]
        print("[watchdog] delete ignore", path)
        return
    
    if delete_image(file):
        print(f"[watchdog] File deleted: {path}")
    else:
        print(f"[watchdog] Error deleting file: {path}")

    with dict_lock:
        _ = deleted_files.pop(file.name)

class ImageChangeHandler(FileSystemEventHandler):
    def __init__(self):
        super().__init__()
        

    def on_created(self, event):
        file  = Path(event.src_path).resolve()

        if is_image(file) == False or is_file_ready(event.src_path) == False:
            return
        
        print(f"[watchdog - Detected] File created: {event.src_path}")

        file_path = file.as_posix()
        mtime = file.stat().st_mtime
        
        with dict_lock:
            dfile_path, dmtime = deleted_files.get(file.name, (None, None))
            if dfile_path is not None and datetime.fromtimestamp(mtime) == dmtime:
                moved_files[file_path] = dfile_path
                deleted_files.pop(file.name)
                is_move = True
            else:
                created_files[file_path] = mtime
                may_moved_files[file.name] = (file_path, mtime)
                is_move = False
        
        if is_move:
            threading.Timer(DELAY_TIME*5, move, args=(file_path, file.stat().st_mtime)).start()
        else:
            threading.Timer(DELAY_TIME*2, create, args=(file_path, file.stat().st_mtime)).start()

    def on_modified(self, event):
        file  = Path(event.src_path).resolve()

        if is_image(file) == False or is_file_ready(event.src_path) == False:
            return
        
        print("[watchdog - Detected] File modified:", event.src_path)

        file_path = file.as_posix()
        mtime = file.stat().st_mtime

        if only_update_metadata(file):
            print("[watchdog] Modify ignore: ", event.src_path)
            return
    
        with dict_lock:
            if file_path in modified_files or file_path in moved_files or file_path in created_files:
                # file is processing
                print("[watchdog] Modify ignore: ", event.src_path)
                return
            
            modified_files[file_path] = mtime
        
        threading.Timer(DELAY_TIME, update, args=(file_path, mtime)).start()

    def on_deleted(self, event):
        file = Path(event.src_path).resolve()

        if not is_image(file):
            return
        
        print(f"[watchdog - Detected] File deleted: {event.src_path}")

        file_path = file.as_posix()

        image = query_images_by_path(file)
        if image is None:
            return
        
        mtime = image.last_modified

        is_move = False
        is_delete = False
        with dict_lock:
            cfile_path, cmtime = may_moved_files.get(file.name, (None, None))
            if cmtime is not None and datetime.fromtimestamp(cmtime) == mtime:
                moved_files[cfile_path] = file_path
                is_move = True
                may_moved_files.pop(file.name)
                created_files.pop(cfile_path, None)
            elif file.name not in deleted_files:
                is_delete = True
                deleted_files[file.name] = (file_path, mtime)
            else:
                print("[watchdog] delete error", file_path)

        if is_move:
            threading.Timer(DELAY_TIME, move, args=(cfile_path, cmtime)).start()
        elif is_delete:
            threading.Timer(DELAY_TIME*4, delete, args=(file_path, mtime)).start()

    def on_moved(self, event):
        # it is rename
        src = Path(event.src_path).resolve()
        dst = Path(event.dest_path).resolve()
        print(f"[watchdog - Detected] File moved: {event.src_path} -> {event.dest_path}")

        if not is_image(dst):
            return
        
        is_rename = is_image(src)
        # rename from temproal file, take the same action as modify
        is_update = not is_image(src) 

        file_path = dst.as_posix()
        mtime = dst.stat().st_mtime

        
        if is_rename:
            with dict_lock:
                moved_files[file_path] = src.as_posix()
            threading.Timer(DELAY_TIME, move, args=(file_path, mtime)).start()

        elif is_update:
            with dict_lock:
                modified_files[file_path] = mtime
        
            threading.Timer(DELAY_TIME, update, args=(file_path, mtime)).start()
        else:
            print(f"[watchdog] move error")

class WatchdogService:
    def __init__(self):
        self.observer = Observer()
        self.handler = ImageChangeHandler()
        self.watches = {}
    
    def add(self, path: Path):

        path = path.resolve()

        if path.is_dir() == False:
            return False
        if path in self.watches:
            return True
        
        print(f"[watchdog] Watching {path}")
        #self.observer.stop()
        watch = self.observer.schedule(self.handler, str(path), recursive=False)
        self.watches[path.as_posix()] = watch

        return True

    def remove(self, path: Path):
        path = path.resolve()

        if path.is_dir() == False or (path.as_posix() not in self.watches):
            return False
        
        print(f"[watchdog] Stop Watching {path}")

        watch = self.watches.pop(path.as_posix())
        self.observer.unschedule(watch)

        return True


    def start(self):
        paths = get_all_listening_paths()
        print(f"[watchdog] Starting...")
        for path in paths:
            self.add(Path(path))
        
        self.observer.start()

    def stop(self):
        print(f"[watchdog] Stopping...")
        self.observer.stop()
        self.observer.join()
