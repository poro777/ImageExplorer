from typing import List
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


def query_images_by_id_list(ids: List[int]):
    with Session(engine) as session:
        if len(ids) == 0:
            return []
        statement = select(Image).where(Image.id.in_(ids))
        results = session.exec(statement).all()

        def convert(image: Image):
            result = dict(image)
            result["directory"] = image.directory.path
            return result

        return list(map(convert, results))
    