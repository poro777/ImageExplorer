from database.database import engine
from sqlmodel import Session, select
from database.models import Directory, Image


def get_directory_id(path: str) -> int | None:
    with Session(engine) as session:
        directory = session.exec(select(Directory).where(Directory.path == path)).first()
        if directory is not None:
            return directory.id
        else:
            return None