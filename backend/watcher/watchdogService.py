# watcher.py
from datetime import datetime
import os
import time
from typing import Dict, Optional
from sqlmodel import Session
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from pathlib import Path
import threading

from database.database import engine

from router.file_api import ALLOWED_EXTENSIONS
from router.sqlite_api import inesrt_or_update_image, delete_image, move_image_path
from database.utils import get_all_listening_paths, query_images_by_path

class ListItem:
    def __init__(self):
        self.is_processing = False
        self.files = []
    def __repr__(self):
        return f"ListItem(is_processing={self.is_processing}, files={self.files})"
    

dict_lock = threading.Lock()
run_thread = False
list_lock = threading.Lock()
# {file base: items}
waitting_list: Dict[str, ListItem] = dict()
condition = threading.Condition(lock=list_lock)
DELAY = 1

last_add_time = 0

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
        
class FileChangeType:
    CREATED = "created"
    DELETED = "deleted"
    MODIFIED = "modified"
    MOVED = "moved"
    REPLACED = "replaced"

class ChangedFile:
    def __init__(self, src: Path,  change_type: str, mtime: datetime, dst: Optional[Path] = None):
        self.src = src.resolve()
        self.dst = dst.resolve() if dst else None
        self.type = change_type
        self.mtime = mtime
        self.time = time.time()

    def _match_move_cond(self, src: Optional[Path], smtime: Optional[datetime], dst: Optional[Path], dmtime: Optional[datetime]):
        if src is None or dst is None or smtime is None or dmtime is None:
            return False
        return (src != dst) and (src.name == dst.name) and (smtime == dmtime)

    def _same_path(self, src: Optional[Path], dst: Optional[Path]):
        if src is None or dst is None:
            return False
        return (src == dst)
    
    def change_type(self, type: str, path: Path = None, mtime: datetime = None):
        '''
            input type: create, delete, modify
        '''
        
        path = path.resolve() if path else None
        match self.type:
            case FileChangeType.CREATED:
                if type == FileChangeType.DELETED and self._match_move_cond(self.src, self.mtime, path, mtime):
                    # with same basename and mtime, consider it as a move
                    self.type = FileChangeType.MOVED
                    self.dst = self.src
                    self.src = path
                elif type == FileChangeType.MODIFIED and self._same_path(self.src, path):
                    # if modified, keep the same src and update mtime
                    self.type = FileChangeType.MODIFIED
                    self.mtime = mtime
                else:
                    print(f"[watchdog] Change type mismatch: {self.type} -> {type}", self.src, path)
                    return False
                
            case FileChangeType.DELETED:
                if type == FileChangeType.CREATED and self._match_move_cond(self.src, self.mtime, path, mtime):
                    # with same basename and mtime, consider it as a move
                    self.type = FileChangeType.MOVED
                    self.dst = path
                elif type == FileChangeType.DELETED and not self._same_path(self.src, path):
                    # TODO: delete with same basename but different path
                    # consider it as a move and replace if there is create later.
                    return False
                else:
                    print(f"[watchdog] Change type mismatch: {self.type} -> {type}", self.src, path)
                    return False
                
            case FileChangeType.MODIFIED: 
                if type == FileChangeType.MODIFIED and self._same_path(self.src, path):
                    self.mtime = mtime
                elif type == FileChangeType.DELETED and self._same_path(self.src, path):
                    # if deleted, keep the same src and update mtime
                    self.type = FileChangeType.DELETED
                    self.mtime = mtime
                else:
                    print(f"[watchdog] Change type mismatch: {self.type} -> {type}", self.src, path)
                    return False
                
            case FileChangeType.MOVED:
                print(f"[watchdog] Change type mismatch: {self.type} -> {type}", self.src, path)
                return False
            case FileChangeType.REPLACED:
                print(f"[watchdog] Change type mismatch: {self.type} -> {type}", self.src, path)
                return False
            case _:
                raise ValueError(f"Unknown change type: {type}")
            
        self.time = time.time()
        return True
    
    def __repr__(self):
        return f"ChangedFile(src={self.src}, change_type={self.type}, dst={self.dst})"

def process_file(file: ChangedFile, id):
    print(f"[watchdog - Processing - {id}] {file.type} {file.src} -> {file.dst if file.dst else 'N/A'}")
    file_path = file.src.as_posix()
    if file.type == FileChangeType.CREATED or file.type == FileChangeType.MODIFIED:
        with Session(engine) as session:
            try:
                if inesrt_or_update_image(file_path, session) is not None:
                    print(f"[watchdog - Result - {id}] {file.type} image: {file_path}")
                else:
                    if file.type == FileChangeType.MODIFIED:
                        print(f"[watchdog - Result - {id}] Modify ignore: ", file_path)
                    else:
                        print(f"[watchdog - Result - {id}] Error {file.type} image: {file_path}")
            except Exception as e:
                print(f'[watchdog - Result - {id}] Error during {file.type}: {e}')

    elif file.type == FileChangeType.DELETED:
        if delete_image(file.src):
            print(f"[watchdog - Result - {id}] File deleted: {file_path}")
        else:
            print(f"[watchdog - Result - {id}] Error deleting file: {file_path}")

    elif file.type == FileChangeType.MOVED:
        if move_image_path(file.src, file.dst, False):
            print(f"[watchdog - Result - {id}] Move image: {file.src} -> {file.dst}")
        else:
            print(f"[watchdog - Result - {id}] Error moving image: {file.src} -> {file.dst}")

def add_file(src: Path, type: str, mtime: datetime, dst: Optional[Path] = None):
    global last_add_time
    src = src.resolve()
    dst = dst.resolve() if dst else None
    with condition:
        if src.name in waitting_list:
            for file in waitting_list[src.name].files:
                if file.change_type(type, src, mtime):
                    break
            else:
                file = ChangedFile(src, type, mtime, dst)
                waitting_list[src.name].files.append(file)
        else:
            file = ChangedFile(src, type, mtime, dst)
            waitting_list.setdefault(src.name, ListItem()).files.append(file)

        last_add_time = time.time()
        condition.notify()  # Wake up the processor thread

def process_waitting_list(id):
    global run_thread, last_add_time
    while run_thread:
        item = None

        with condition:
            while len(waitting_list) == 0:
                condition.wait()  # Sleep until notified
                if not run_thread:
                    return
                print(f"[watchdog - Thread {id}] Woke up at time {datetime.fromtimestamp(time.time())}")

            if last_add_time + DELAY > time.time(): # wait for all files change are done
                continue
            
            for name, item in list(waitting_list.items()):
                if item.is_processing:
                    continue
                
                if len(item.files) != 0: 
                    item.is_processing = True # lock the processing flag
                    break

            else:
                # If no file was found, continue to the next iteration
                continue
        
        while True: # process the files in the list until the list is empty
            with list_lock:
                file = item.files.pop(0)

            process_file(file, id)
            
            with list_lock:
                if len(item.files) == 0:
                    item.is_processing = False # unlock the processing flag
                    break
            
        
        
 
class ImageChangeHandler(FileSystemEventHandler):
    def __init__(self):
        super().__init__()
        

    def on_created(self, event):
        file  = Path(event.src_path).resolve()

        if is_image(file) == False or is_file_ready(event.src_path) == False:
            return
        
        print(f"[watchdog - Detected] File created: {event.src_path}")

        mtime = datetime.fromtimestamp(file.stat().st_mtime)
        
        add_file(file, FileChangeType.CREATED, mtime)

    def on_modified(self, event):
        file  = Path(event.src_path).resolve()

        if is_image(file) == False or is_file_ready(event.src_path) == False:
            return
        
        print("[watchdog - Detected] File modified:", event.src_path)

        mtime = datetime.fromtimestamp(file.stat().st_mtime)

        if only_update_metadata(file):
            print("[watchdog] Modify ignore: ", event.src_path)
            return
    
        add_file(file, FileChangeType.MODIFIED, mtime)

    def on_deleted(self, event):
        file = Path(event.src_path).resolve()

        if not is_image(file):
            return
        
        print(f"[watchdog - Detected] File deleted: {event.src_path}")

        image = query_images_by_path(file)
        if image is None:
            return
        
        mtime = image.last_modified

        add_file(file, FileChangeType.DELETED, mtime)

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

        mtime = datetime.fromtimestamp(dst.stat().st_mtime)

        
        if is_rename:
            add_file(src, FileChangeType.MOVED, mtime, dst)

        elif is_update:
            add_file(dst, FileChangeType.MODIFIED, mtime, None)
        else:
            print(f"[watchdog] move error")

class WatchdogService:
    def __init__(self):
        self.observer = Observer()
        self.handler = ImageChangeHandler()
        self.watches = {}
        self.process_threads = []
        self.N = 3
        for i in range(self.N):
            self.process_threads.append(threading.Thread(target=process_waitting_list, args=(i,), daemon=True))
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
        global run_thread
        paths = get_all_listening_paths()
        print(f"[watchdog] Starting...")
        for path in paths:
            self.add(Path(path))
        run_thread = True
        for process_thread in self.process_threads:
            process_thread.start()
        self.observer.start()

    def stop(self):
        global run_thread
        print(f"[watchdog] Stopping...")
        while True:
            with condition:
                run_thread = False
                condition.notify(self.N)
            for process_thread in self.process_threads:
                process_thread.join()
            if not any(thread.is_alive() for thread in self.process_threads):
                break
        self.observer.stop()
        self.observer.join()
