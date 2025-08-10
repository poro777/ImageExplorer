
from tests.utils import *
from tests.constants import *

import indexer
indexer.COLLECTION_NAME = "test_collection"

from datetime import datetime
from pathlib import Path
from fastapi.testclient import TestClient
import pytest

import indexer

from router.file_api import getPathOfImageFile, BASE_DIR
import router.file_api

from PIL import Image as ImageLoader

from router.sqlite_api import inesrt_or_update_image
from sqlmodel import Session, SQLModel, create_engine


def test_getPathOfImageFile():
    # Test with a valid image file
    def vaild_image(file_path: str):
        image = Path(BASE_DIR / file_path).resolve()
        valid_image = getPathOfImageFile(file_path)
        assert valid_image is not None and valid_image.as_posix() == image.as_posix()

        valid_image = getPathOfImageFile(image.as_posix())
        assert valid_image is not None and valid_image.as_posix() == image.as_posix()

        valid_image = getPathOfImageFile(str(image))
        assert valid_image is not None and valid_image.as_posix() == image.as_posix()

    vaild_image(PATH_HUSKY_IMAGE)
    vaild_image(PATH_HUSKY_IMAGE_2)
    vaild_image(PATH_ROBOT_IMAGE)
    vaild_image(PATH_ROBOT_IMAGE_2)

    # Test with an invalid image file
    invalid_image = getPathOfImageFile("not_existing.jpg")
    assert invalid_image is None

    # Test with a non-image file
    non_image_file = getPathOfImageFile("not_existing.txt")
    assert non_image_file is None

    # Test with a non-image file
    non_image_file = getPathOfImageFile(BASE_DIR)
    assert non_image_file is None



def test_root(client: TestClient):
    response = client.get("/")

    data = response.json()  

    assert response.status_code == 200  
    assert data["Good"] == "v8"  

def test_empyt_database(client: TestClient):
    wait_before_read_vecdb()
    # sqlite db
    response = client.get("/image")
    data = response.json()

    assert response.status_code == 200
    assert len(data) == 0  # Assuming no images are present initially

    # vectore db
    response = client.get("/api/list")
    data = response.json()

    assert response.status_code == 200
    assert len(data) == 0  # Assuming no images are present initially

def test_add_images(client: TestClient):

    def add_image(id, file_path: str):
        test_image_path = getPathOfImageFile(file_path)
        if test_image_path is None:
            pytest.fail(f"Test image {file_path} not found")
        try:
            test_image = ImageLoader.open(test_image_path)
        except Exception as e:
            pytest.fail(f"Test image {file_path} cannot be opened: {e}")

        response = client.post("/image/create", params={"file": file_path})
        data = response.json()

        assert response.status_code == 200
        assert data["id"] == id
        assert data["filename"] == test_image_path.name
        assert data["full_path"] == test_image_path.as_posix()
        assert data["width"] == test_image.width
        assert data["height"] == test_image.height
        assert data["last_modified"] == datetime.fromtimestamp(test_image_path.stat().st_mtime).isoformat()
        assert data["thumbnail_path"] is not None
        thumbnail_path = Path(data["thumbnail_path"])
        assert thumbnail_path.is_absolute() == False # only base name should be returned
        assert (router.file_api.THUMBNAIL_DIR / data["thumbnail_path"]).exists()

    add_image(1, PATH_HUSKY_IMAGE)
    add_image(2, PATH_ROBOT_IMAGE_2)

    wait_before_read_vecdb()
    
    # sqlite db
    response = client.get("/image")
    data = response.json()
    assert response.status_code == 200
    assert len(data) == 2

    # vector db
    response = client.get("/api/list")
    data = response.json()

    assert response.status_code == 200
    assert len(data) == 2
    assert "husky" in data['1']
    assert "robot" in data['2']

def test_update_images(client: TestClient, session: Session, tmp_images_path: Path):
    inesrt_or_update_image((tmp_images_path / PATH_HUSKY_IMAGE).as_posix(), session)
    rename_file(tmp_images_path / SUBFOLDER, HUSKY_IMAGE_2, HUSKY_IMAGE)
    

    response = client.get("/image/lookup", params={"file": (tmp_images_path / PATH_HUSKY_IMAGE).resolve()})
    assert response.status_code == 200
    data = response.json()
    id = data["id"]
    last_modified = data["last_modified"]
    thumbnail_path = Path(data["thumbnail_path"])
    assert data["filename"] == HUSKY_IMAGE
    assert data["full_path"] == (tmp_images_path / PATH_HUSKY_IMAGE).resolve().as_posix()
    assert thumbnail_path.is_absolute() == False  # only base name should be returned
    assert (router.file_api.THUMBNAIL_DIR / thumbnail_path).exists()

    replace_file(tmp_images_path / SUBFOLDER, tmp_images_path, HUSKY_IMAGE)
    inesrt_or_update_image((tmp_images_path / PATH_HUSKY_IMAGE).as_posix(), session)

    response = client.get("/image/lookup", params={"file": (tmp_images_path / PATH_HUSKY_IMAGE).resolve()})
    assert response.status_code == 200
    data = response.json()
    assert id == data["id"]
    assert data["last_modified"] == datetime.fromtimestamp((tmp_images_path / PATH_HUSKY_IMAGE).stat().st_mtime).isoformat()

    assert data["filename"] == HUSKY_IMAGE
    assert data["full_path"] == (tmp_images_path / PATH_HUSKY_IMAGE).resolve().as_posix()

    new_thumbnail_path = Path(data["thumbnail_path"])
    assert new_thumbnail_path != thumbnail_path
    assert Path(new_thumbnail_path).is_absolute() == False
    assert Path(router.file_api.THUMBNAIL_DIR / new_thumbnail_path).exists()
    assert Path(router.file_api.THUMBNAIL_DIR / thumbnail_path).exists() == False  # old thumbnail should be deleted

def test_add_not_existing_image(client: TestClient):
    response = client.post("/image/create", params={"file": "not_existing.jpg"})
    assert response.status_code == 404

    response = client.post("/image/create", params={"file": "not_existing.txt"})
    assert response.status_code == 404

    response = client.post("/image/create", params={"file": "not_existing"})
    assert response.status_code == 404

    wait_before_read_vecdb()

    # sqlite db
    response = client.get("/image")
    data = response.json()

    assert response.status_code == 200
    assert len(data) == 0  # Assuming no images are present initially

    # vectore db
    response = client.get("/api/list")
    data = response.json()

    assert response.status_code == 200
    assert len(data) == 0  # Assuming no images are present initially




def test_lookup_image(client: TestClient, session: Session):
    inesrt_or_update_image(PATH_HUSKY_IMAGE, session)
    inesrt_or_update_image(PATH_ROBOT_IMAGE_2, session)

    wait_before_read_vecdb()

    response = client.get("/image/lookup", params={"file": PATH_HUSKY_IMAGE})
    data = response.json()
    assert response.status_code == 200
    assert data["id"] == 1
    assert data["filename"] == HUSKY_IMAGE

    robotFile = getPathOfImageFile(PATH_ROBOT_IMAGE_2)
    
    response = client.get("/image/lookup", params={"file": PATH_ROBOT_IMAGE_2})
    data = response.json()
    assert response.status_code == 200
    assert data["id"] == 2
    assert data["filename"] == ROBOT_IMAGE_2

    response = client.get("/image/lookup", params={"file": robotFile.as_posix()})
    data = response.json()
    assert response.status_code == 200
    assert data["id"] == 2
    assert data["filename"] == ROBOT_IMAGE_2


    # test_lookup_non_existing_image
    response = client.get("/image/lookup", params={"file": "not_existing.jpg"})
    assert response.status_code == 404

    # existing file but not in the database
    assert getPathOfImageFile(PATH_FLOWER_IMAGE) is not None
    # this file is not in the database, so it should return 404
    response = client.get("/image/lookup", params={"file": PATH_FLOWER_IMAGE})
    assert response.status_code == 404



def test_delete_images(client: TestClient, session: Session):
    inesrt_or_update_image(PATH_ROBOT_IMAGE, session)
    inesrt_or_update_image(PATH_HUSKY_IMAGE, session)
    

    id = 1
    response = client.delete(f"/image/{id}")
    assert response.status_code == 200

    wait_before_read_vecdb()

    # sqlite db
    response = client.get("/image")
    data = response.json()
    assert response.status_code == 200
    assert len(data) == 1
    assert data[0]["id"] == 2 # husky should remain
    assert data[0]["thumbnail_path"] is not None

    # check if the thumbnail is deleted
    thumbnail_path : Path= router.file_api.THUMBNAIL_DIR / data[0]["thumbnail_path"]
    assert Path(data[0]["thumbnail_path"]).is_absolute() == False # only base name should be returned
    assert thumbnail_path.exists()

    # vector db
    response = client.get("/api/list")
    data = response.json()
    assert response.status_code == 200
    assert len(data) == 1
    assert '2' in data  # husky should remain

    # delete the remaining image
    id = 2
    response = client.delete(f"/image/{id}")
    assert response.status_code == 200

    wait_before_read_vecdb()
    # sqlite db
    response = client.get("/image")
    data = response.json()
    assert response.status_code == 200
    assert len(data) == 0
    assert len(list(router.file_api.THUMBNAIL_DIR.glob("*"))) == 0  # all thumbnails should be deleted

    # vector db
    response = client.get("/api/list")
    data = response.json()
    assert response.status_code == 200
    assert len(data) == 0

    # try to delete non-existing image
    id = 3
    response = client.delete(f"/image/{id}")
    assert response.status_code == 404


def test_delete_all_images(client: TestClient, session: Session):
    inesrt_or_update_image(PATH_ROBOT_IMAGE, session)
    inesrt_or_update_image(PATH_HUSKY_IMAGE, session)
    inesrt_or_update_image(PATH_FLOWER_IMAGE, session)

    response = client.delete("/image/delete_all")
    assert response.status_code == 200

    wait_before_read_vecdb()
    # sqlite db
    response = client.get("/image")
    data = response.json()
    assert response.status_code == 200
    assert len(data) == 0
    assert len(list(router.file_api.THUMBNAIL_DIR.glob("*"))) == 0  # all thumbnails should be deleted

    # vector db
    response = client.get("/api/list")
    data = response.json()
    assert response.status_code == 200
    assert len(data) == 0

    # try to delete empty database
    response = client.delete("/image/delete_all")
    assert response.status_code == 200

def test_list_vecdb(client: TestClient, session: Session, tmp_path: Path):

    response = client.get("/api/list")
    data = response.json()

    assert response.status_code == 200
    assert len(data) == 0

    inesrt_or_update_image(PATH_ROBOT_IMAGE, session)
    inesrt_or_update_image(PATH_HUSKY_IMAGE_2, session)

    wait_before_read_vecdb()

    response = client.get("/api/list")
    data = response.json()

    assert response.status_code == 200
    assert len(data) == 2
    assert '1' in data
    assert '2' in data


    abs_path = BASE_DIR.resolve().as_posix()
    response = client.get("/api/list", params={"path":abs_path})
    data = response.json()

    assert response.status_code == 200
    assert len(data) == 1
    assert '1' in data

    relative_path = SUBFOLDER # relative to BASE_DIR
    response = client.get("/api/list", params={"path":relative_path})
    data = response.json()

    assert response.status_code == 200
    assert len(data) == 1
    assert '2' in data

    response = client.get("/api/list", params={"path":tmp_path.as_posix()})
    
    assert response.status_code == 404





