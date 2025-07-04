from fastapi.testclient import TestClient
from sqlmodel import Session
from tests.constants import *
from tests.utils import *

from watcher import fs_watcher
from watcher.watchdogService import *

from router.sqlite_api import delete_image, inesrt_or_update_image
from router.file_api import getPathOfImageFile

from datetime import datetime, timedelta

def test_ChangedFile_OTHER():
    file_path = getPathOfImageFile(PATH_HUSKY_IMAGE)
    mtime = datetime.now()
    
    try:
        file = ChangedFile(file_path, "OtherType", mtime)
    except ValueError:
        assert True
    else:
        assert False


    file = ChangedFile(file_path, FileChangeType.CREATED, mtime)
    try:
        file.change_type("OtherType", file_path, mtime)
    except ValueError:
        assert True
    else:
        assert False


def test_ChangedFile_MODIFIED(tmp_path: Path):
    file_path = getPathOfImageFile(PATH_HUSKY_IMAGE)
    mtime = datetime.now()
    file = ChangedFile(file_path, FileChangeType.MODIFIED, mtime)

    # 'modify' again, update mtime
    new_mtime = mtime + timedelta(seconds=1)
    changed = file.change_type(FileChangeType.MODIFIED, file_path, new_mtime)

    assert changed == True
    assert file.type == FileChangeType.MODIFIED and file.mtime == new_mtime

    # 'modify' then 'delete' file, change type to delete
    new_mtime = mtime + timedelta(seconds=2)
    changed = file.change_type(FileChangeType.DELETED, file_path, new_mtime)

    assert changed == True
    assert file.type == FileChangeType.DELETED and file.mtime == new_mtime

    # no 'create' after 'modify'
    file = ChangedFile(file_path, FileChangeType.MODIFIED, mtime)
    new_mtime = mtime + timedelta(seconds=3)
    changed = file.change_type(FileChangeType.CREATED, file_path, new_mtime)
    assert changed == False
    assert file.type == FileChangeType.MODIFIED

    # no 'move' after 'modify'
    changed = file.change_type(FileChangeType.MOVED, file_path, new_mtime)
    assert changed == False
    assert file.type == FileChangeType.MODIFIED


    # 'modify' again, but not same file
    another_file_path = tmp_path / PATH_HUSKY_IMAGE
    changed = file.change_type(FileChangeType.MODIFIED, another_file_path, new_mtime)
    assert changed == False
    assert file.type == FileChangeType.MODIFIED and file.mtime == mtime



def test_ChangedFile_CREATE(tmp_path: Path):
    file_path = getPathOfImageFile(PATH_HUSKY_IMAGE)
    mtime = datetime.now()
    file = ChangedFile(file_path, FileChangeType.CREATED, mtime)

    # 'create' then 'modify'
    new_mtime = mtime + timedelta(seconds=1)
    changed = file.change_type(FileChangeType.MODIFIED, file_path, new_mtime)

    assert changed == True
    assert file.type == FileChangeType.MODIFIED and file.mtime == new_mtime

    # 'create' follow 'delete' 
    # same mtime and filename => change to 'move'
    file = ChangedFile(file_path, FileChangeType.CREATED, mtime)
    old_path = tmp_path / PATH_HUSKY_IMAGE
    changed = file.change_type(FileChangeType.DELETED, old_path, mtime)

    assert changed == True
    assert file.type == FileChangeType.MOVED and file.mtime == mtime
    assert file.src == old_path and file.dst == file_path

    # 'create' follow 'delete'
    # same file path => change to 'delete'
    file = ChangedFile(file_path, FileChangeType.CREATED, mtime)
    changed = file.change_type(FileChangeType.DELETED, file_path, mtime)

    assert changed == True
    assert file.type == FileChangeType.DELETED and file.mtime == mtime


    # 'create' follow 'delete'
    # different basename
    file = ChangedFile(file_path, FileChangeType.CREATED, mtime)
    another_path = tmp_path / PATH_FLOWER_IMAGE
    changed = file.change_type(FileChangeType.DELETED, another_path, mtime)

    assert changed == False
    assert file.type == FileChangeType.CREATED and file.mtime == mtime

    # 'create' follow 'delete'
    # different mtime
    file = ChangedFile(file_path, FileChangeType.CREATED, mtime)
    old_path = tmp_path / PATH_HUSKY_IMAGE
    new_mtime = mtime + timedelta(seconds=2)
    changed = file.change_type(FileChangeType.DELETED, old_path, new_mtime)

    assert changed == False
    assert file.type == FileChangeType.CREATED and file.mtime == mtime


    # no 'create' after 'create'
    file = ChangedFile(file_path, FileChangeType.CREATED, mtime)
    new_mtime = mtime + timedelta(seconds=2)
    changed = file.change_type(FileChangeType.CREATED, file_path, new_mtime)
    assert changed == False
    assert file.type == FileChangeType.CREATED

    # no 'move' after 'create'
    changed = file.change_type(FileChangeType.MOVED, file_path, new_mtime)
    assert changed == False
    assert file.type == FileChangeType.CREATED


def test_ChangedFile_DELETE(tmp_path: Path):
    file_path = getPathOfImageFile(PATH_HUSKY_IMAGE)
    mtime = datetime.now()

    # 'delete' follow 'create' 
    # same mtime and filename => change to 'move'
    file = ChangedFile(file_path, FileChangeType.DELETED, mtime)
    new_path = tmp_path / PATH_HUSKY_IMAGE
    changed = file.change_type(FileChangeType.CREATED, new_path, mtime)

    assert changed == True
    assert file.type == FileChangeType.MOVED and file.mtime == mtime
    assert file.src == file_path and file.dst == new_path

    # 'delete' follow 'create'
    # but same file path
    file = ChangedFile(file_path, FileChangeType.DELETED, mtime)
    new_mtime = mtime + timedelta(seconds=2)
    changed = file.change_type(FileChangeType.CREATED, file_path, mtime)

    assert changed == False
    assert file.type == FileChangeType.DELETED and file.mtime == mtime


    # 'delete' follow 'create'
    # different basename
    file = ChangedFile(file_path, FileChangeType.DELETED, mtime)
    another_path = tmp_path / PATH_FLOWER_IMAGE
    changed = file.change_type(FileChangeType.CREATED, another_path, mtime)

    assert changed == False
    assert file.type == FileChangeType.DELETED and file.src == file_path and file.mtime == mtime

    # 'create' follow 'delete'
    # different mtime
    file = ChangedFile(file_path, FileChangeType.DELETED, mtime)
    new_path = tmp_path / PATH_HUSKY_IMAGE
    new_mtime = mtime + timedelta(seconds=2)
    changed = file.change_type(FileChangeType.CREATED, new_path, new_mtime)

    assert changed == False
    assert file.type == FileChangeType.DELETED and file.src == file_path and file.mtime == mtime


    # no 'delete' after 'delete'
    file = ChangedFile(file_path, FileChangeType.DELETED, mtime)
    new_mtime = mtime + timedelta(seconds=2)
    changed = file.change_type(FileChangeType.DELETED, file_path, new_mtime)
    assert changed == False
    assert file.type == FileChangeType.DELETED

    file = ChangedFile(file_path, FileChangeType.DELETED, mtime)
    another_path = tmp_path / PATH_FLOWER_IMAGE
    changed = file.change_type(FileChangeType.DELETED, another_path, mtime)
    assert changed == False
    assert file.type == FileChangeType.DELETED and file.src == file_path


    # no 'move' after 'delete'
    changed = file.change_type(FileChangeType.MOVED, file_path, new_mtime)
    assert changed == False
    assert file.type == FileChangeType.DELETED  



def test_ChangedFile_MOVE():
    file_path = getPathOfImageFile(PATH_HUSKY_IMAGE)
    mtime = datetime.now()

    file = ChangedFile(file_path, FileChangeType.MOVED, mtime)

    changed = file.change_type(FileChangeType.MOVED, file_path, mtime)
    assert changed == False
    assert file.type == FileChangeType.MOVED

    changed = file.change_type(FileChangeType.MODIFIED, file_path, mtime)
    assert changed == False
    assert file.type == FileChangeType.MOVED


    changed = file.change_type(FileChangeType.DELETED, file_path, mtime)
    assert changed == False
    assert file.type == FileChangeType.MOVED

    changed = file.change_type(FileChangeType.CREATED, file_path, mtime)
    assert changed == False
    assert file.type == FileChangeType.MOVED
