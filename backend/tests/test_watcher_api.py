from fastapi.testclient import TestClient
import pytest
from sqlmodel import Session
from tests.constants import *
from tests.utils import *

from watcher.watchdogService import *

from router.sqlite_api import delete_image, inesrt_or_update_image
from router.file_api import getPathOfImageFile

from datetime import datetime, timedelta

from PIL import Image as ImageLoader
from PIL.ImageFile import ImageFile


@pytest.mark.timeout(60)
def test_watchdog_add_api(client: TestClient, session: Session, fs_watcher: WatchdogService, tmp_images_path: Path):    
    base = tmp_images_path
    subfolder = tmp_images_path / SUBFOLDER

    response = client.post("/watcher/add", params={"path": base.as_posix()})
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 3, "Expected 3 images in the base folder"

    response = client.get("/watcher/listening")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["path"] == base.as_posix()

    delete_file(base / HUSKY_IMAGE)

    wait_watchdog_done()

    response = client.get("/image")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2, "Expected 2 images after deletion"
    assert not any(image["filename"] == HUSKY_IMAGE for image in data), "Husky image should be deleted"

@pytest.mark.timeout(60)
def test_watchdog_remove(client: TestClient, session: Session, fs_watcher: WatchdogService, tmp_images_path: Path):
    base = tmp_images_path
    subfolder = tmp_images_path / SUBFOLDER
    
    response = client.post("/watcher/add", params={"path": base.as_posix()})
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 3, "Expected 3 images in the base folder"

    response = client.get("/watcher/listening")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["path"] == base.as_posix()

    response = client.delete("/watcher/remove", params={"path": base.as_posix()})
    assert response.status_code == 200

    response = client.get("/watcher/listening")
    assert response.status_code == 200
    assert len(response.json()) == 0
    
    delete_file(base / HUSKY_IMAGE)

    wait_watchdog_done()

    response = client.get("/image")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 3


@pytest.mark.timeout(60)
def test_watchdog_remove_and_clear(client: TestClient, session: Session, fs_watcher: WatchdogService, tmp_images_path: Path):    
    base = tmp_images_path
    subfolder = tmp_images_path / SUBFOLDER
    
    response = client.post("/watcher/add", params={"path": subfolder.as_posix()})

    response = client.post("/watcher/add", params={"path": base.as_posix()})
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 3, "Expected 3 images in the base folder"

    response = client.get("/watcher/listening")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2

    response = client.delete("/watcher/remove", params={"path": base.as_posix(), "delete_images": True})
    assert response.status_code == 200

    response = client.get("/watcher/listening")
    assert response.status_code == 200
    assert len(response.json()) == 1
    
    delete_file(base / HUSKY_IMAGE)

    wait_watchdog_done()

    response = client.get("/image")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2

    response = client.get("/image/folder", params={"path": base.as_posix()})
    assert response.status_code == 200
    assert len(response.json()) == 0, "Expected no images in the base folder after removal"
