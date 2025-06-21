from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pathlib import Path
from fastapi import Depends
from sqlmodel import Session, select, text
from database import models
from typing import List, Optional, Union
from PIL import Image as ImageLoader
from database.models import Image, Directory
from database.database import get_session
from database import database
from sqlalchemy.exc import IntegrityError

import indexer

from router.file_api import getFolder, getImageFile
from datetime import datetime

router = APIRouter(
    prefix="/image",
    tags=["sqlite_db"],
)

def mapFolder(image: Image):
    result = dict(image)
    result['directory'] = image.directory.path
    return result

@router.get("/")
def read_images(session: Session = Depends(get_session)):
    images = session.exec(select(Image)).all()
    
    return list(map(mapFolder, images))

# DELETE /images
@router.delete("/delete_all")
def delete_all_images(session: Session = Depends(get_session)):
    session.exec(text("DELETE FROM image"))  # or session.query(Image).delete()
    session.commit()
    # override a new vector db
    indexer.create_embed_db(indexer.COLLECTION_NAME)
    return {"detail": "All images deleted"}

@router.post("/create", response_model=Image)
def create_image(file: str, session: Session = Depends(get_session)):
    file:Path = getImageFile(file)

    if file is None:
        raise HTTPException(status_code=404, detail="File not found")

    try:
        pil_image = ImageLoader.open(file)
    except Exception as e:
        print(e)
        raise HTTPException(status_code=400, detail="Cannot open the image")
    
    path = file.parent.as_posix()
    name = file.name
    
    directory = session.exec(select(Directory).where(Directory.path == path)).first()
    if not directory:
        directory = Directory(path=path, is_watching=False)
        session.add(directory)
        session.commit()
        session.refresh(directory)

    image = Image(directory_id=directory.id, filename=name, 
                  width=pil_image.width, height=pil_image.height, 
                  last_modified=datetime.fromtimestamp(file.stat().st_mtime))
    session.add(image)

    try:
        session.commit()
        session.refresh(image)
    except IntegrityError as e:
        session.rollback()
        raise HTTPException(
            status_code=400,
            detail=f"Cannot insert image: {e}"
        )
    
    def rollback(e):
        session.delete(image)
        session.commit()
        raise HTTPException(
            status_code=400,
            detail=f"Cannot insert image: {e}"
        )

    try:
        if indexer.insert_image(image.id, name, pil_image, image.directory_id) == False:
            rollback("Vector db insert failed")
    except Exception as e:
        rollback(e)
    
    return image

# DELETE /images/{image_id}
@router.delete("/{image_id}")
def delete_image(image_id: int, session: Session = Depends(get_session)):
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
@router.get("/lookup")
def get_image_file(file: str, session: Session = Depends(get_session)):
    file:Path = getImageFile(file)

    if file is None:
        raise HTTPException(status_code=404, detail="File not found")
    
    path = file.parent.as_posix()
    name = file.name

    directory = session.exec(
        select(Directory).where(Directory.path == path)
    ).first()

    if not directory:
        raise HTTPException(status_code=404, detail="Directory not found")

    # Lookup the image by directory_id and filename
    image = session.exec(
        select(Image).where(
            Image.directory_id == directory.id,
            Image.filename == name
        )
    ).first()

    if not image:
        raise HTTPException(status_code=404, detail="Image not found")
    
    return mapFolder(image)


# GET /images/by-folder?path=/data/images/cats/
@router.get("/folder")
def get_images_by_folder(path: str, session: Session = Depends(get_session)):
    path = getFolder(path)

    if path is None:
        raise HTTPException(status_code=404, detail="Directory not found")
    
    path = path.as_posix()

    directory = session.exec(
        select(Directory).where(Directory.path == path)
    ).first()

    if not directory:
        raise HTTPException(status_code=404, detail="Directory not found")
    
    return list(map(mapFolder, directory.images))
