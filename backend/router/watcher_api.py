from fastapi import APIRouter, HTTPException
from pathlib import Path
from fastapi import Depends
from sqlmodel import Session, delete, select, text
from typing import List
from PIL import Image as ImageLoader
from database.models import Image, Directory
from database.database import get_session

import indexer

from router.file_api import getFolderPath, getPathOfImageFile, ALLOWED_EXTENSIONS
from datetime import datetime
from watcher import fs_watcher, get_N_files


router = APIRouter(
    prefix="/watcher",
    tags=["watcher"],
)

@router.get("/")
def watcher_is_ready():
    return "Ok" if (get_N_files() == 0) else "Not ready"


@router.post("/add", response_model=List[Image])
def add_path_to_listener(path: str, session: Session = Depends(get_session)):
    '''inesrt or update a batch of files in a folder'''
    path:Path = getFolderPath(path)

    if path is None:
        raise HTTPException(status_code=404, detail="Path not found")
    
    directory = session.exec(select(Directory).where(Directory.path == path.as_posix())).first()
    if not directory:
        directory = Directory(path=path.as_posix(), is_watching=True, last_modified=datetime.fromtimestamp(path.stat().st_mtime))
        session.add(directory)
        session.commit()
        session.refresh(directory)
    else:
        directory.is_watching = True
        directory.last_modified = datetime.fromtimestamp(path.stat().st_mtime)
        session.commit()
    
    images = []
    for file in path.iterdir():
        file = getPathOfImageFile(file)
        if file is not None:
            name = file.name

            image = session.exec(select(Image).where(
                Image.directory_id == directory.id,
                Image.filename == name)
            ).first()
            
            try:
                if image is not None: # image already exists
                    if image.last_modified is not None and image.last_modified == datetime.fromtimestamp(file.stat().st_mtime):
                        continue # file not modified

                    pil_image = ImageLoader.open(file)
                    image.last_modified = datetime.fromtimestamp(file.stat().st_mtime)
                    image.width=pil_image.width
                    image.height=pil_image.height

                else:
                    pil_image = ImageLoader.open(file)
                    image = Image(directory_id=directory.id, filename=name, 
                                width=pil_image.width, height=pil_image.height, 
                                last_modified=datetime.fromtimestamp(file.stat().st_mtime),
                                full_path=file.resolve().as_posix())
                    session.add(image)

                session.commit()
                session.refresh(image)
                if indexer.insert_image(indexer.COLLECTION_NAME, image.id, name, pil_image, image.directory_id) == False:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Cannot insert image to vector db."
                    )
                
                images.append(image.model_dump())

            except Exception as e:
                print(e)
                continue
            

    fs_watcher.add(path)
    return images


@router.delete("/remove")
def remove_path_from_listener(path: str, delete_images: bool = False, session: Session = Depends(get_session)):
    path:Path = getFolderPath(path)

    if path is None:
        raise HTTPException(status_code=404, detail="Path not found")
    
    if fs_watcher.remove(path) == False:
        raise HTTPException(status_code=400, detail="Path is not listening")

    directory = session.exec(
        select(Directory).where(Directory.path == path.as_posix())
    ).first()

    if directory is None:
        raise HTTPException(status_code=404, detail="Directory not found")
    
    try:
        directory.is_watching = False
        if delete_images:
            indexer.delete_by_list(indexer.COLLECTION_NAME, [image.id for image in directory.images])
            session.exec(delete(Image).where(Image.directory_id == directory.id))
        session.commit()
    except Exception as e:
        raise HTTPException(status_code=500, detail="Cannot delete images")

@router.get("/listening", response_model=List[Directory])
def get_listening_paths(session: Session = Depends(get_session)):
    directories = session.exec(select(Directory).where(Directory.is_watching == True)).all()
    return directories