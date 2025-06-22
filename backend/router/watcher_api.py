import os
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

from router.file_api import getFolder, getImageFile, ALLOWED_EXTENSIONS
from datetime import datetime

router = APIRouter(
    prefix="/dir",
    tags=["directory"],
)


@router.post("/add", response_model=List[Image])
def create_image(path: str, session: Session = Depends(get_session)):
    path:Path = getFolder(path)

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
    
    files = []
    for file in path.iterdir():
        if file.is_file() and file.suffix.lower() in ALLOWED_EXTENSIONS:

            try:
                pil_image = ImageLoader.open(file)
            except Exception as e:
                print(e)
                continue
            name = file.name

            image = session.exec(select(Image).where(
                Image.directory_id == directory.id,
                Image.filename == name)
            ).first()
            
            if image is not None: # image already exised
                continue

            image = Image(directory_id=directory.id, filename=name, 
                        width=pil_image.width, height=pil_image.height, 
                        last_modified=datetime.fromtimestamp(file.stat().st_mtime))
            session.add(image)
            files.append((image, name, pil_image))

    try:
        session.flush()
        for image, name, pil_image in files:
            if indexer.insert_image(image.id, name, pil_image, image.directory_id) == False:
                session.rollback()
                raise HTTPException(
                    status_code=400,
                    detail=f"Cannot insert image to vector db."
                )

        session.commit()
        
    except Exception as e:
        session.rollback()
        raise HTTPException(
            status_code=400,
            detail=f"Cannot insert image: {e}"
        )
    
    images = []
    for image, _, _ in files:
        session.refresh(image)
        images.append(image)

    return images