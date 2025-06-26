import time
import indexer
indexer.COLLECTION_NAME = "test_collection"  # Set a test collection name, before importing the app


from datetime import datetime
from pathlib import Path
from fastapi.testclient import TestClient
import pytest
from sqlmodel import Session, SQLModel, create_engine

from database.database import get_session

import indexer.vector_db
from main import app

from sqlmodel.pool import StaticPool  
from router.file_api import getPathOfImageFile
from PIL import Image as ImageLoader
from router.sqlite_api import inesrt_or_update_image

def clear_vector_db():
    """Clear the vector database for testing purposes."""
        # Clear the vector database collection before each test
    ids = [data[indexer.vector_db.FIELD_ID] for data in indexer.list_data(indexer.COLLECTION_NAME)]
    if indexer.delete_by_list(indexer.COLLECTION_NAME, ids) == False:
        raise RuntimeError("Failed to clear vector database collection")


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        yield session


@pytest.fixture(name="client")  
def client_fixture(session: Session):  
    def get_session_override():  
        return session

    app.dependency_overrides[get_session] = get_session_override  

    client = TestClient(app)  
    yield client  
    app.dependency_overrides.clear()  


def test_root():
    client = TestClient(app)  

    response = client.get("/")

    data = response.json()  

    assert response.status_code == 200  
    assert data["Good"] == "v8"  

def test_empyt_database(client: TestClient):
    clear_vector_db()
    time.sleep(0.5)
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
    clear_vector_db()

    def add_image(id, file_name: str):
        test_image_path = getPathOfImageFile(file_name)
        if test_image_path is None:
            pytest.fail(f"Test image {file_name} not found")
        try:
            test_image = ImageLoader.open(test_image_path)
        except Exception as e:
            pytest.fail(f"Test image {file_name} cannot be opened: {e}")

        response = client.post("/image/create", params={"file": test_image_path.name})
        data = response.json()

        assert response.status_code == 200
        assert data["id"] == id
        assert data["filename"] == test_image_path.name
        assert data["full_path"] == test_image_path.as_posix()
        assert data["width"] == test_image.width
        assert data["height"] == test_image.height
        assert data["last_modified"] == datetime.fromtimestamp(test_image_path.stat().st_mtime).isoformat()

    
    add_image(1, "husky_2.jpg")
    add_image(2, "robot_1.jpg")

    time.sleep(0.5)
    
    response = client.get("/api/list")
    data = response.json()

    assert response.status_code == 200
    assert len(data) == 2
    for i in range(2):
        if data[i][indexer.vector_db.FIELD_ID] == 1:
            assert "husky" in data[0][indexer.vector_db.FIELD_TEXT]
        elif data[i][indexer.vector_db.FIELD_ID] == 2:
            assert "robot" in data[1][indexer.vector_db.FIELD_TEXT]


def test_query_images(client: TestClient, session: Session):
    clear_vector_db()

    def add_image(id, file_name: str):
        test_image_path = getPathOfImageFile(file_name)
        if test_image_path is None:
            pytest.fail(f"Test image {file_name} not found")
        try:
            test_image = ImageLoader.open(test_image_path)
        except Exception as e:
            pytest.fail(f"Test image {file_name} cannot be opened: {e}")

        response = client.post("/image/create", params={"file": test_image_path.name})
        data = response.json()

        assert response.status_code == 200
        assert data["id"] == id
        assert data["filename"] == test_image_path.name
        assert data["full_path"] == test_image_path.as_posix()
        assert data["width"] == test_image.width
        assert data["height"] == test_image.height
        assert data["last_modified"] == datetime.fromtimestamp(test_image_path.stat().st_mtime).isoformat()

    
    add_image(1, "husky_2.jpg")
    add_image(2, "robot_1.jpg")

    time.sleep(0.5)

    response = client.get("/api/query", params={"text": "husky", "use_text_embed": False, "use_bm25": False, "use_joint_embed": False})
    data = response.json()

    assert response.status_code == 200
    assert len(data) == 0

    response = client.get("/api/query", params={"text": "husky", "use_text_embed": True, "use_bm25": True, "use_joint_embed": True})
    data = response.json()

    print(data)
    assert response.status_code == 200
    assert data[0]["id"] == 1

    response = client.get("/api/query", params={"text": "robot", "use_text_embed": True, "use_bm25": True, "use_joint_embed": True})
    data = response.json()

    assert response.status_code == 200
    assert data[0]["id"] == 2