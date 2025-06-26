from typing import List
from database.database import engine
from sqlmodel import Session, select
from database.models import Directory, Image
from pathlib import Path

def get_directory_id(path: str) -> int | None:
    with Session(engine) as session:
        directory = session.exec(select(Directory).where(Directory.path == path)).first()
        if directory is not None:
            return directory.id
        else:
            return None

def query_images_by_id_list(ids: List[int]):
    with Session(engine) as session:
        if len(ids) == 0:
            return []
        statement = select(Image).where(Image.id.in_(ids))
        results = session.exec(statement).all()

        return results

def query_images_by_path(path: Path):
    with Session(engine) as session:
        statement = select(Image).where(Image.full_path == path.as_posix())
        results = session.exec(statement).first()

        return results
      
def get_all_listening_paths():
    with Session(engine) as session:
        statement = select(Directory).where(Directory.is_watching == True)
        results = session.exec(statement).all()

        return list(map(lambda x: x.path, results))


