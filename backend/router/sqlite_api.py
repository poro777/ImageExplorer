from fastapi import APIRouter, HTTPException
from pathlib import Path
from fastapi import Depends
from sqlmodel import Session, select, text
from typing import List, Optional
from PIL import Image as ImageLoader
from PIL.ImageFile import ImageFile
from database.models import Image, Directory
from database.database import get_session
from database import database

import indexer

from router.file_api import getFolderPath, getPathOfImageFile, create_thumbnail, delete_all_thumbnails
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
    
    # Delete all images from vector db
    while True:
        ids = list(indexer.list_data(indexer.COLLECTION_NAME).keys())
        if len(ids) == 0:
            break
        delete = indexer.delete_by_list(indexer.COLLECTION_NAME, ids)
        if delete == False:
            raise HTTPException(
                status_code=500,
                detail="Vector db delete failed"
            )
    delete_all_thumbnails()
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
        thumbnail_path = create_thumbnail(pil_image, ext=file.suffix)
        image = Image(directory_id=directory.id, filename=name, 
                  width=pil_image.width, height=pil_image.height, 
                  last_modified=datetime.fromtimestamp(file.stat().st_mtime,),
                  full_path=file.as_posix(), thumbnail_path=thumbnail_path.as_posix())
        session.add(image)
    else:
        if image.last_modified is not None and image.last_modified == datetime.fromtimestamp(file.stat().st_mtime):
            # file not modified
            return None
        
        pil_image = loadImage(file)
        thumbnail_path = create_thumbnail(pil_image, ext=file.suffix)
        image.width=pil_image.width
        image.height=pil_image.height
        image.last_modified = datetime.fromtimestamp(file.stat().st_mtime)
        if image.thumbnail_path is not None:
            Path(image.thumbnail_path).unlink(missing_ok=True)
        image.thumbnail_path = thumbnail_path.as_posix()

    try:
        session.commit()
        session.refresh(image)

    except Exception as e:
        session.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Cannot insert image: {e}"
        )
    
    if indexer.insert_image(indexer.COLLECTION_NAME, image.id, name, pil_image, image.directory_id) == False:
        raise HTTPException(
            status_code=500,
            detail="Vector db insert failed"
        )
    return image


@router.post("/create", response_model=Optional[Image])
def create_image(file: str, session: Session = Depends(get_session)):
    return inesrt_or_update_image(file, session)


def delete_image(file: Path, session: Session):
    id = None
    image = session.exec(select(Image).where(Image.full_path == file.as_posix())).first()

    if image is None:
        return False
    id = image.id
    successed = indexer.delete_one(indexer.COLLECTION_NAME, image.id)
    if successed == False:
        return False
        
    try:
        image = session.get(Image, id)
        if image.thumbnail_path is not None:
            Path(image.thumbnail_path).unlink(missing_ok=True)
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
    if image.thumbnail_path is not None:
        Path(image.thumbnail_path).unlink(missing_ok=True)
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


def move_image_path(current: Path, new: Path, replace = False, session: Session = None):
    '''move image from current path to new path
        input absolute path
    '''
    
    curr_path = current.parent.as_posix()
    curr_name = current.name
    
    new_path = new.parent.as_posix()
    new_name = new.name

    

    image = session.exec(select(Image).where(Image.full_path == current.as_posix())).first()

    if image is None:
        print(f"Error moving image: file {current.as_posix()} not found in database.")
        return False

    target_image = session.exec(select(Image).where(Image.full_path == new.as_posix())).first()

    # Make sure the file names are the same
    replace = replace and curr_name == new_name
    if target_image is not None and replace == False:
        print(f"Error moving image: file {new.as_posix()} already exists.")
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
        print(f"Error moving image: {e}")
        session.rollback()
        return False
    
    if indexer.change_partition(indexer.COLLECTION_NAME, image.id, str(new_dorectory.id)) == False:
        print(f"Error moving image: {new.as_posix()} in vector db")
        return False

    return True



