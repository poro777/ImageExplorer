import indexer
import time
import shutil
from pathlib import Path
from pathlib import Path
import indexer
from watcher.watchdogService import get_N_files, DELAY

def copy_file(src_folder: Path, dst_folder: Path, filename: str):
    if src_folder == dst_folder:
        return

    src = src_folder / filename
    dst = dst_folder / filename
    assert src.is_file()
    shutil.copy(src, dst)
    assert dst.is_file(), "copy failed"


def move_file(src_folder: Path, dst_folder: Path, filename: str):
    src = src_folder / filename
    dst = dst_folder / filename
    assert src.is_file()
    assert dst.exists() == False, "use replace_file instead"
    shutil.move(src, dst)

    assert dst.is_file() and src.exists() == False, "move failed"

def delete_file(filePath: Path):
    assert filePath.is_file()
    filePath.unlink()

    assert filePath.exists() == False, "delete failed"


def rename_file(src_folder: Path, filename: str, new_filename: str):
    file = src_folder / filename
    new_file = src_folder / new_filename
    assert file.is_file()
    assert new_file.exists() == False, "file already exists, use replace_file instead"
    file.rename(new_file)

def replace_file(src_folder: Path, dst_folder: Path, filename: str):
    file = src_folder / filename
    new_file = dst_folder / filename
    assert file.is_file()
    assert new_file.is_file(), "no file to replace, use move_file instead"
    file.replace(new_file)


def wait_before_read_vecdb():
    time.sleep(0.5)


def clear_vector_db():
    """Clear the vector database for testing purposes.""" 
    while True:
        ids = list(indexer.list_data(indexer.COLLECTION_NAME).keys())
        if len(ids) == 0:
            break
        delete = indexer.delete_by_list(indexer.COLLECTION_NAME, ids)
        if delete == False:
            raise RuntimeError("Failed to clear vector database collection")

def wait_watchdog_done():
    """Waits for the watchdog service to process all pending file events.

    This function polls the number of files in the watchdog's waiting list
    and exits when the list is empty.
    """
    time.sleep(DELAY) # wait event start
    while get_N_files() > 0:
        time.sleep(0.1)