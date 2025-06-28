import time

import database.database
import database.utils
import indexer
import watcher.watchdogService
indexer.COLLECTION_NAME = "test_collection"


from datetime import datetime
from pathlib import Path
from fastapi.testclient import TestClient
import pytest
from sqlmodel import Session, SQLModel, create_engine

import database

import indexer
from main import app

from sqlmodel.pool import StaticPool  
from router.file_api import getPathOfImageFile, BASE_DIR
from PIL import Image as ImageLoader
from router.sqlite_api import inesrt_or_update_image

import watcher

PATH_HUSKY_IMAGE = "husky_1.jpg"
PATH_HUSKY_IMAGE_2 = "folder/husky_2.jpg"
PATH_ROBOT_IMAGE = "robot_1.jpg"
PATH_ROBOT_IMAGE_2 = "folder/robot_2.jpg"
PATH_FLOWER_IMAGE = "flower.jpg"

def wait_before_read_vecdb():
    time.sleep(0.5)


def clear_vector_db():
    """Clear the vector database for testing purposes."""
        # Clear the vector database collection before each test
    if indexer.is_collection_exist(indexer.COLLECTION_NAME) == False:
        indexer.create_embed_db(indexer.COLLECTION_NAME)

    while True:
        ids = [data[indexer.FIELD_ID] for data in indexer.list_data(indexer.COLLECTION_NAME)]
        if len(ids) == 0:
            break
        delete = indexer.delete_by_list(indexer.COLLECTION_NAME, ids)
        if delete == False:
            raise RuntimeError("Failed to clear vector database collection")


@pytest.fixture(name="session")
def session_fixture(monkeypatch):
    test_engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )

    # Patch the global engine in your app code
    monkeypatch.setattr(database.database, "engine", test_engine)
    monkeypatch.setattr(database.utils, "engine", test_engine)
    monkeypatch.setattr(watcher.watchdogService, "engine", test_engine)
    assert database.database.engine is test_engine
    assert database.utils.engine is test_engine
    assert watcher.watchdogService.engine is test_engine

    SQLModel.metadata.create_all(test_engine)

    with Session(test_engine) as session:
        yield session

@pytest.fixture(name="client")  
def client_fixture(session: Session):  
    def get_session_override():  
        return session

    app.dependency_overrides[database.database.get_session] = get_session_override  

    client = TestClient(app)  
    yield client  
    app.dependency_overrides.clear()  

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



def test_root():
    client = TestClient(app)  

    response = client.get("/")

    data = response.json()  

    assert response.status_code == 200  
    assert data["Good"] == "v8"  

def test_empyt_database(client: TestClient):
    clear_vector_db()
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

    clear_vector_db()
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
    for i in range(2):
        if data[i][indexer.vector_db.FIELD_ID] == 1:
            assert "husky" in data[0][indexer.vector_db.FIELD_TEXT]
        elif data[i][indexer.vector_db.FIELD_ID] == 2:
            assert "robot" in data[1][indexer.vector_db.FIELD_TEXT]


def test_add_not_existing_image(client: TestClient):
    clear_vector_db()
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



def test_query_images(client: TestClient, session: Session):

    def query(text: str, use_text_embed: bool, use_bm25: bool, use_joint_embed: bool):
        assert use_text_embed or use_bm25 or use_joint_embed, "At least one of the query methods must be used"
        response = client.get("/api/query", params={
            "text": text,
            "use_text_embed": use_text_embed,
            "use_bm25": use_bm25,
            "use_joint_embed": use_joint_embed
        })
        
        data = sorted(response.json(), key=lambda x: x['distance'], reverse=True) 
        assert response.status_code == 200
        assert len(data) >= 2 # at least two result should be returned
        assert text in data[0]["filename"] and text in data[1]["filename"]

    clear_vector_db()
    inesrt_or_update_image(PATH_HUSKY_IMAGE, session)
    inesrt_or_update_image(PATH_HUSKY_IMAGE_2, session)
    inesrt_or_update_image(PATH_ROBOT_IMAGE, session)
    inesrt_or_update_image(PATH_ROBOT_IMAGE_2, session)

    wait_before_read_vecdb()

    response = client.get("/image")
    data = response.json()

    assert response.status_code == 200
    assert len(data) == 4

    response = client.get("/api/query", params={"text": "husky", "use_text_embed": False, "use_bm25": False, "use_joint_embed": False})
    data = response.json()
    assert response.status_code == 200
    assert len(data) == 0

    query("husky", True, True, True)  
    query("robot", True, True, True) 
    query("husky", True, False, False)
    query("robot", True, False, False)
    query("husky", False, True, False)
    query("robot", False, True, False)
    query("husky", False, False, True)
    query("robot", False, False, True)


def test_lookup_image(client: TestClient, session: Session):
    clear_vector_db()
    inesrt_or_update_image(PATH_HUSKY_IMAGE, session)
    inesrt_or_update_image(PATH_ROBOT_IMAGE_2, session)

    wait_before_read_vecdb()

    response = client.get("/image/lookup", params={"file": PATH_HUSKY_IMAGE})
    data = response.json()
    assert response.status_code == 200
    assert data["id"] == 1
    assert data["filename"] == getPathOfImageFile(PATH_HUSKY_IMAGE).name

    robotFile = getPathOfImageFile(PATH_ROBOT_IMAGE_2)
    
    response = client.get("/image/lookup", params={"file": PATH_ROBOT_IMAGE_2})
    data = response.json()
    assert response.status_code == 200
    assert data["id"] == 2
    assert data["filename"] == robotFile.name

    response = client.get("/image/lookup", params={"file": robotFile.as_posix()})
    data = response.json()
    assert response.status_code == 200
    assert data["id"] == 2
    assert data["filename"] == robotFile.name


    # test_lookup_non_existing_image
    response = client.get("/image/lookup", params={"file": "not_existing.jpg"})
    assert response.status_code == 404

    # existing file but not in the database
    assert getPathOfImageFile(PATH_FLOWER_IMAGE) is not None
    # this file is not in the database, so it should return 404
    response = client.get("/image/lookup", params={"file": PATH_FLOWER_IMAGE})
    assert response.status_code == 404



def test_delete_images(client: TestClient, session: Session):
    clear_vector_db()
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

    # vector db
    response = client.get("/api/list")
    data = response.json()
    assert response.status_code == 200
    assert len(data) == 1
    assert data[0][indexer.vector_db.FIELD_ID] == 2  # husky should remain

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
    clear_vector_db()
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
    # vector db
    response = client.get("/api/list")
    data = response.json()
    assert response.status_code == 200
    assert len(data) == 0

    # try to delete empty database
    response = client.delete("/image/delete_all")
    assert response.status_code == 200
