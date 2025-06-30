
import pytest
from fastapi.testclient import TestClient


import database.database
import database.utils

from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool  

import watcher.watchdogService

import indexer
indexer.COLLECTION_NAME = "test_collection"

from main import app

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
