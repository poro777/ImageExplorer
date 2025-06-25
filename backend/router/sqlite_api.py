from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pathlib import Path
from fastapi import Depends
from sqlmodel import Session, select, text
from database import models
from typing import List, Optional, Union
from PIL import Image as ImageLoader
from PIL.ImageFile import ImageFile
from database.models import Image, Directory
from database.database import get_session
from database import database
from sqlalchemy.exc import IntegrityError

import indexer

from router.file_api import getFolderPath, getPathOfImageFile
from datetime import datetime

router = APIRouter(
    prefix="/image",
    tags=["sqlite_db"],
)



@router.get("/")
def read_images(session: Session = Depends(get_session)):
    images = session.exec(select(Image)).all()
    return images

# DELETE /images
@router.delete("/delete_all")
def delete_all_images(session: Session = Depends(get_session)):
    session.exec(text("DELETE FROM image"))  # or session.query(Image).delete()
    session.commit()
    # override a new vector db
    indexer.create_embed_db(indexer.COLLECTION_NAME)
    return {"detail": "All images deleted"}


def loadImage(file: Path) -> ImageFile:
    try:
        pil_image = ImageLoader.open(file)
        return pil_image
    except Exception as e:
        raise HTTPException(status_code=400, detail="Cannot open the image")

def inesrt_or_update_image(file: str, session: Session):
    file:Path = getPathOfImageFile(file)

    if file is None:
        raise HTTPException(status_code=404, detail="File not found")
    
    path = file.parent.as_posix()
    name = file.name

    directory = session.exec(select(Directory).where(Directory.path == path)).first()
    if not directory:
        directory = Directory(path=path, is_watching=False)
        session.add(directory)
        session.commit()
        session.refresh(directory)


    image = session.exec(select(Image).where(Image.full_path == file.as_posix())).first()

    if image is None:
        pil_image = loadImage(file)
        image = Image(directory_id=directory.id, filename=name, 
                  width=pil_image.width, height=pil_image.height, 
                  last_modified=datetime.fromtimestamp(file.stat().st_mtime,),
                  full_path=file.as_posix())
        session.add(image)
    else:
        if image.last_modified is not None and image.last_modified == datetime.fromtimestamp(file.stat().st_mtime):
            # file not modified
            return None
        
        pil_image = loadImage(file)
        image.width=pil_image.width
        image.height=pil_image.height
        image.last_modified = datetime.fromtimestamp(file.stat().st_mtime)

    try:
        session.commit()
        session.refresh(image)

    except Exception as e:
        session.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Cannot insert image: {e}"
        )
    
    if indexer.insert_image(image.id, name, pil_image, image.directory_id) == False:
        session.delete(image)
        session.commit()
        raise HTTPException(
            status_code=500,
            detail="Vector db insert failed"
        )
    return image


@router.post("/create", response_model=Optional[Image])
def create_image(file: str, session: Session = Depends(get_session)):
    return inesrt_or_update_image(file, session)


def delete_image(file: Path):
    id = None
    with Session(database.engine) as session:
        image = session.exec(select(Image).where(Image.full_path == file.as_posix())).first()

        if image is None:
            return False
        id = image.id
        successed = indexer.delete_one(indexer.COLLECTION_NAME, image.id)
        if successed == False:
            return False
        
    with Session(database.engine) as session:
        try:
            image = session.get(Image, id)
            session.delete(image)
            session.commit()

            return True
        except Exception as e:
            print(f"Error deleting image: {e}")
            return False

# DELETE /images/{image_id}
@router.delete("/{image_id}")
def delete_image_by_id(image_id: int, session: Session = Depends(get_session)):
    image = session.get(Image, image_id)
    if not image:
        raise HTTPException(status_code=404, detail="Image not found")
    
    successed = indexer.delete_one(indexer.COLLECTION_NAME, image.id)
    if successed == False:
        raise HTTPException(status_code=500, detail="Vector db delete failed")
    session.delete(image)
    session.commit()
    return {"detail": "Image deleted"}

# GET /images/lookup?file=...
@router.get("/lookup", response_model=Image)
def get_image_file(file: str, session: Session = Depends(get_session)):
    file:Path = getPathOfImageFile(file)

    if file is None:
        raise HTTPException(status_code=404, detail="File not found")
    
    image = session.exec(select(Image).where(Image.full_path == file.as_posix())).first()

    if not image:
        raise HTTPException(status_code=404, detail="Image not found")
    
    return image


# GET /images/by-folder?path=/data/images/cats/
@router.get("/folder", response_model=List[Image])
def get_images_by_folder(path: str, session: Session = Depends(get_session)):
    path = getFolderPath(path)

    if path is None:
        raise HTTPException(status_code=404, detail="Directory not found")
    
    path = path.as_posix()

    directory = session.exec(
        select(Directory).where(Directory.path == path)
    ).first()

    if not directory:
        raise HTTPException(status_code=404, detail="Directory not found")
    
    return directory.images
