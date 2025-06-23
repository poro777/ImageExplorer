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


def move_image_path(current: Path, new: Path, replace = False):
    '''move image from current path to new path
        input absolute path
    '''
    
    with Session(engine) as session:
        curr_path = current.parent.as_posix()
        curr_name = current.name
        
        new_path = new.parent.as_posix()
        new_name = new.name

        

        image = session.exec(select(Image).where(Image.full_path == current.as_posix())).first()

        if image is None:
            return False

        target_image = session.exec(select(Image).where(Image.full_path == new.as_posix())).first()

        # Make sure the file names are the same
        replace = replace and curr_name == new_name
        if target_image is not None and replace == False:
            return False

        try:
            if target_image is not None:
                session.delete(target_image)

            new_dorectory = session.exec(select(Directory).where(Directory.path == new_path)).first()
            if not new_dorectory:
                new_dorectory = Directory(path=new_path, is_watching=False)
                session.add(new_dorectory)
                session.flush()

            image.directory_id = new_dorectory.id
            image.filename = new_name
            image.full_path = new.as_posix()
            
            session.commit()
        except Exception as e:
            session.rollback()
            return False
        
        return True



