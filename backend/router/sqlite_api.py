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

from indexer import vector_db

from router.file_api import getFolder, getImageFile

router = APIRouter(
    prefix="/image",
    tags=["sqlite_db"],
)



@router.get("/", response_model=List[Image])
def read_images(session: Session = Depends(get_session)):
    return session.exec(select(Image)).all()

# DELETE /images
@router.delete("/delete_all")
def delete_all_images(session: Session = Depends(get_session)):
    session.exec(text("DELETE FROM image"))  # or session.query(Image).delete()
    session.commit()
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

    image = Image(directory_id=directory.id, filename=name, width=pil_image.width, height=pil_image.height)
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
    
    try:
        vector_db.insert_image(image.id, file.as_posix(), pil_image)
    except Exception as e:
        image = session.get(Image, image.id)
        session.delete(image)
        session.commit()
        raise HTTPException(
            status_code=400,
            detail=f"Cannot insert image: {e}"
        )
    
    return image

# DELETE /images/{image_id}
@router.delete("/{image_id}")
def delete_image(image_id: int, session: Session = Depends(get_session)):
    image = session.get(Image, image_id)
    if not image:
        raise HTTPException(status_code=404, detail="Image not found")
    session.delete(image)
    session.commit()
    return {"detail": "Image deleted"}

# GET /images/lookup?file=...
@router.get("lookup", response_model=Optional[Image])
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
    
    return image


# GET /images/by-folder?path=/data/images/cats/
@router.get("/folder", response_model=List[Image])
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
    
    return directory.images
