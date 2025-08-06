from fastapi.testclient import TestClient
import pytest
from sqlmodel import Session
from tests.constants import *
from tests.utils import *

from watcher.watchdogService import *

from router.sqlite_api import delete_image, inesrt_or_update_image
from router.file_api import getPathOfImageFile
import router.file_api

from datetime import datetime, timedelta

from PIL import Image as ImageLoader
from PIL.ImageFile import ImageFile


@pytest.mark.timeout(60)
def test_watchdog_create(client: TestClient, session: Session, fs_watcher: WatchdogService, tmp_images_path: Path):    
    base = tmp_images_path
    subfolder = tmp_images_path / SUBFOLDER

    fs_watcher.add(base)
    fs_watcher.add(subfolder)

    copy_file(base, subfolder, HUSKY_IMAGE)
    copy_file(subfolder, base, HUSKY_IMAGE_2)

    wait_watchdog_done()
    
    response = client.get("/image")
    data = response.json()
    assert response.status_code == 200
    assert len(data) == 2
    assert data[0]["thumbnail_path"] is not None
    assert Path(router.file_api.THUMBNAIL_DIR / data[0]["thumbnail_path"]).exists()

    response = client.get("/image/lookup", params={"file": (subfolder / HUSKY_IMAGE).as_posix()})
    data = response.json()
    assert response.status_code == 200
    assert data["filename"] == HUSKY_IMAGE

    response = client.get("/image/lookup", params={"file": (base / HUSKY_IMAGE_2).as_posix()})
    data = response.json()
    assert response.status_code == 200
    assert data["filename"] == HUSKY_IMAGE_2

@pytest.mark.timeout(60)
def test_watchdog_move(client: TestClient, session: Session, fs_watcher: WatchdogService, tmp_images_path: Path):
    base = tmp_images_path
    subfolder = tmp_images_path / SUBFOLDER

    fs_watcher.add(base)
    fs_watcher.add(subfolder)

    images = [HUSKY_IMAGE, FLOWER_IMAGE, ROBOT_IMAGE]
    for image in images:
        file = base / image
        moved_file = subfolder / image
        inesrt_or_update_image(file.as_posix(), session)

    wait_before_read_vecdb()

    response = client.get("/image")
    data = response.json()
    thumbnail_paths = {}
    
    assert response.status_code == 200
    assert len(data) == len(images)

    for image in images:
        file = base / image
        response = client.get("/image/lookup", params={"file": file.as_posix()})
        assert response.status_code == 200

        data = response.json()
        thumbnail_path = data["thumbnail_path"]
        assert thumbnail_path is not None
        assert Path(router.file_api.THUMBNAIL_DIR / thumbnail_path).exists()
        thumbnail_paths[image] = thumbnail_path
        

    response = client.get("api/list", params={"path": base.as_posix()})
    assert response.status_code == 200
    assert len(response.json()) == len(images)

    response = client.get("api/list", params={"path": subfolder.as_posix()})
    assert response.status_code == 404

    for image in images:
        move_file(base, subfolder, image)

    wait_watchdog_done()
    
    response = client.get("/image")
    data = response.json()
    assert response.status_code == 200
    assert len(data) == len(images)

    for image in images:
        moved_file = subfolder / image
        response = client.get("/image/lookup", params={"file": moved_file.as_posix()})
        assert response.status_code == 200
        data = response.json()
        assert thumbnail_paths[image] == data["thumbnail_path"]
        assert Path(router.file_api.THUMBNAIL_DIR / thumbnail_path).exists()

    wait_before_read_vecdb()

    response = client.get("api/list", params={"path": base.as_posix()})
    assert response.status_code == 200
    assert len(response.json()) == 0

    response = client.get("api/list", params={"path": subfolder.as_posix()})
    assert response.status_code == 200
    assert len(response.json()) == len(images)

def test_watchdog_delete(client: TestClient, session: Session, fs_watcher: WatchdogService, tmp_images_path: Path):
    base = tmp_images_path

    fs_watcher.add(base)
    images = [HUSKY_IMAGE, FLOWER_IMAGE, ROBOT_IMAGE]
    for image in images:
        file = base / image
        inesrt_or_update_image(file.as_posix(), session)
    wait_before_read_vecdb()

    response = client.get("/image")
    data = response.json()
    assert response.status_code == 200
    assert len(data) == len(images)
    
    delete_file(base / HUSKY_IMAGE)
    wait_watchdog_done()
    response = client.get("/image")
    data = response.json()
    assert response.status_code == 200
    assert len(data) == 2

    delete_file(base / FLOWER_IMAGE)
    wait_watchdog_done()
    response = client.get("/image")
    data = response.json()
    assert response.status_code == 200
    assert len(data) == 1
    assert data[0]["full_path"] == (base / ROBOT_IMAGE).as_posix()

    assert Path(router.file_api.THUMBNAIL_DIR /  data[0]["thumbnail_path"]).exists()
    assert len(list(router.file_api.THUMBNAIL_DIR.glob("*"))) == 1  # one thumbnail should remain

def test_watchdog_rename(client: TestClient, session: Session, fs_watcher: WatchdogService, tmp_images_path: Path):
    from io import BytesIO

    base = tmp_images_path

    fs_watcher.add(base)
    file = base / HUSKY_IMAGE
    new_file = base / ("renamed_" + HUSKY_IMAGE)

    inesrt_or_update_image(file.as_posix(), session)
    wait_before_read_vecdb()

    response = client.get("/image/lookup", params={"file": file.as_posix()})
    assert response.status_code == 200
    thubnail_path = response.json()["thumbnail_path"]
    assert Path(router.file_api.THUMBNAIL_DIR / thubnail_path).exists()

    response = client.get("/image/lookup", params={"file": new_file.as_posix()})
    assert response.status_code == 404
    
    

    rename_file(base, HUSKY_IMAGE, new_file.name)

    wait_watchdog_done()

    response = client.get("/image/lookup", params={"file": file.as_posix()})
    assert response.status_code == 404

    response = client.get("/image/lookup", params={"file": new_file.as_posix()})
    assert response.status_code == 200
    assert response.json()["thumbnail_path"] == thubnail_path
    assert Path(router.file_api.THUMBNAIL_DIR / thubnail_path).exists()

def test_watchdog_modify(client: TestClient, session: Session, fs_watcher: WatchdogService, tmp_images_path: Path):
    from io import BytesIO

    base = tmp_images_path

    fs_watcher.add(base)
    file = base / HUSKY_IMAGE
    inesrt_or_update_image(file.as_posix(), session)
    wait_before_read_vecdb()

    response = client.get("/image/lookup", params={"file": file.as_posix()})
    assert response.status_code == 200
    data = response.json()
    thumbnail_path = data["thumbnail_path"]
    assert Path(router.file_api.THUMBNAIL_DIR / thumbnail_path).exists()

    new_file = base / ("renamed_" + HUSKY_IMAGE) # rename to new file to prevent genai cache
    
    rename_file(base, HUSKY_IMAGE, new_file.name)
    
    wait_watchdog_done()

    image: ImageFile = ImageLoader.open(BASE_DIR / FLOWER_IMAGE)
    image.save(new_file, format=image.format)

    wait_watchdog_done()

    response = client.get("/image/lookup", params={"file": new_file.as_posix()})
    assert response.status_code == 200
    data = response.json()
    new_thumbnail_path = data["thumbnail_path"]
    assert new_thumbnail_path != thumbnail_path
    assert Path(router.file_api.THUMBNAIL_DIR / new_thumbnail_path).exists()
    assert Path(router.file_api.THUMBNAIL_DIR / thumbnail_path).exists() == False  # old thumbnail should be deleted

    wait_before_read_vecdb()

    response = client.get("/api/list")
    data = response.json()
    assert response.status_code == 200
    assert '1' in data
    text = data['1']
    assert any((keywork in text) for keywork in ["flower", "floral", "baby's breath"])

    indexer.genai_api.delete_uploaded_file(indexer.genai_api.sanitize_string(new_file.name))

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
