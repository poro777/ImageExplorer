import httpx
import pytest_asyncio
from tests.utils import *
from tests.constants import *

from pathlib import Path
import pytest
from fastapi.testclient import TestClient
import watcher

import database.database

from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool  

import indexer

from main import app
import watcher

import router.file_api

indexer.genai_api.delete_uploaded_files()

@pytest.fixture(name="session")
def session_fixture(monkeypatch):
    test_engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )

    # Patch the global engine in your app code
    monkeypatch.setattr(database.database, "engine", test_engine)
    assert database.database.engine is test_engine

    SQLModel.metadata.create_all(test_engine)

    with Session(test_engine) as session:
        yield session

@pytest.fixture(name="db_session")
def vector_db_fixture(monkeypatch):
    monkeypatch.setattr(indexer, "COLLECTION_NAME", "test_collection")
    assert indexer.COLLECTION_NAME is "test_collection"

    if not indexer.is_collection_exist(indexer.COLLECTION_NAME):
        indexer.create_embed_db(indexer.COLLECTION_NAME)
    else:
        clear_vector_db()

@pytest.fixture(name="client")  
def client_fixture(session: Session, db_session):  
    def get_session_override():  
        return session

    app.dependency_overrides[database.database.get_session] = get_session_override  

    client = TestClient(app)  
    yield client  
    app.dependency_overrides.clear()  

@pytest_asyncio.fixture(name="async_client")
async def async_client_fixture(session: Session, db_session):
    """Async test client fixture using httpx.AsyncClient."""
    
    def get_session_override():
        return session

    app.dependency_overrides[database.database.get_session] = get_session_override
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()
    
@pytest.fixture
def tmp_images_path(tmp_path: Path) -> Path:
    copy_file(BASE_DIR, tmp_path, PATH_HUSKY_IMAGE)
    copy_file(BASE_DIR, tmp_path, PATH_FLOWER_IMAGE)
    copy_file(BASE_DIR, tmp_path, PATH_ROBOT_IMAGE)
    folder = tmp_path / SUBFOLDER
    folder.mkdir()
    copy_file(BASE_DIR, tmp_path, PATH_HUSKY_IMAGE_2)
    copy_file(BASE_DIR, tmp_path, PATH_ROBOT_IMAGE_2)
    
    return tmp_path

@pytest.fixture(name="fs_watcher")
def fs_watcher_fixture(monkeypatch,session: Session):
    '''start watchdog service for tests'''
    fs_watcher = watcher.WatchdogService()

    monkeypatch.setattr(watcher, "fs_watcher", fs_watcher)
    assert watcher.fs_watcher is fs_watcher

    fs_watcher.start()
    yield fs_watcher
    fs_watcher.stop()

@pytest.fixture(autouse=True)
def tmp_thumbnail(tmp_path: Path):
    original = router.file_api.THUMBNAIL_DIR
    router.file_api.THUMBNAIL_DIR = tmp_path / "tmp_thumbnails"
    yield
    router.file_api.THUMBNAIL_DIR = original  # restore original after session

