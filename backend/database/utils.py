from datetime import datetime
from typing import List
from database.database import engine
from sqlmodel import Session, select
from database.models import Directory, Image
from pathlib import Path
from router.file_api import getPathOfImageFile



def get_directory_id(path: str) -> int | None:
    with Session(engine) as session:
        directory = session.exec(select(Directory).where(Directory.path == path)).first()
        if directory is not None:
            return directory.id
        else:
            return None


def mapFolder(image: Image):
    result = dict(image)
    result['directory'] = image.directory.path
    return result

def query_images_by_id_list(ids: List[int]):
    with Session(engine) as session:
        if len(ids) == 0:
            return []
        statement = select(Image).where(Image.id.in_(ids))
        results = session.exec(statement).all()

        return list(map(mapFolder, results))


def move_image_path(current: Path, new: Path):
    '''move image from current path to new path
        input absolute path
    '''
    with Session(engine) as session:
        curr_path = current.parent.as_posix()
        curr_name = current.name
        
        new_path = new.parent.as_posix()
        new_name = new.name

        curr_directory = session.exec(select(Directory).where(Directory.path == curr_path)).first()
        image = session.exec(select(Image).where(
            Image.directory_id == curr_directory.id,
            Image.filename == curr_name)
        ).first()

        if image is None:
            return False
        

        new_dorectory = session.exec(select(Directory).where(Directory.path == new_path)).first()
        if not new_dorectory:
            new_dorectory = Directory(path=new_path, is_watching=False)
            session.add(new_dorectory)
            session.flush()

        image.directory_id = new_dorectory.id
        image.filename = new_name

        try:
            session.commit()
        except Exception as e:
            session.rollback()
            return False
        
        return True



