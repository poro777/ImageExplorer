# database.py
from sqlmodel import SQLModel, create_engine, Session

DATABASE_URL = "sqlite:///./images.db"
engine = create_engine(DATABASE_URL, echo=True)

def init_db():
    #SQLModel.metadata.drop_all(engine)

    SQLModel.metadata.create_all(engine)

def get_session():
    with Session(engine) as session:
        yield session
