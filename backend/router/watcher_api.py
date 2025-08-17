from fastapi import APIRouter, HTTPException
from pathlib import Path
from fastapi import Depends
from sqlmodel import Session, delete, select, text
from typing import Callable, List, Optional
from PIL import Image as ImageLoader
from database.models import Image, Directory
from database.database import get_session
from fastapi import WebSocket, WebSocketDisconnect
from os import stat_result
import indexer

from router.file_api import create_thumbnail, getFolderPath, getPathOfImageFile, ALLOWED_EXTENSIONS
import router.file_api as file_api
from datetime import datetime
import watcher

router = APIRouter(
    prefix="/watcher",
    tags=["watcher"],
)

@router.get("/")
def watcher_is_ready():
    return "Ok" if (watcher.get_N_files() == 0) else "Not ready"


async def process_folder(path: Path, 
    session: Session, 
    progress_cb: Optional[Callable[[int, int], None]] = None) -> List[dict]:
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
    files = [getPathOfImageFile(file) for file in path.iterdir()]
    files = [file for file in files if file is not None]
    total_files = len(files)

    if progress_cb is not None:
        await progress_cb(0, total_files)

    for idx, file in enumerate(files, start=1):
        name = file.name

        file_stat: stat_result = file.stat()

        image = session.exec(select(Image).where(
            Image.directory_id == directory.id,
            Image.filename == name)
        ).first()
        
        try:
            if image is not None: # image already exists
                if image.last_modified is not None and image.last_modified == datetime.fromtimestamp(file_stat.st_mtime) \
                    and image.file_size is not None and image.file_size == file_stat.st_size:
                    if progress_cb is not None:
                        await progress_cb(idx, total_files)
                    continue # file not modified

                pil_image = ImageLoader.open(file)
                thumbnail_path = create_thumbnail(pil_image, ext=file.suffix)
                image.last_modified = datetime.fromtimestamp(file_stat.st_mtime)
                image.width=pil_image.width
                image.height=pil_image.height
                if image.thumbnail_path is not None:
                    (file_api.THUMBNAIL_DIR / image.thumbnail_path).unlink(missing_ok=True)
                image.thumbnail_path = thumbnail_path.name
                image.file_size = file_stat.st_size

            else:
                pil_image = ImageLoader.open(file)
                thumbnail_path = create_thumbnail(pil_image, ext=file.suffix)
                image = Image(directory_id=directory.id, filename=name, 
                            width=pil_image.width, height=pil_image.height, 
                            last_modified=datetime.fromtimestamp(file_stat.st_mtime),
                            full_path=file.resolve().as_posix(), 
                            thumbnail_path=thumbnail_path.name,
                            file_size=file_stat.st_size)
                session.add(image)

            session.commit()
            session.refresh(image)
            if indexer.insert_image(indexer.COLLECTION_NAME, image.id, name, pil_image, image.directory_id) == False:
                raise HTTPException(
                    status_code=400,
                    detail=f"Cannot insert image to vector db."
                )
            
            images.append(image.model_dump(mode="json"))
            if progress_cb is not None:
                await progress_cb(idx, total_files)

        except Exception as e:
            print(e)
            continue

    watcher.fs_watcher.add(path)
    return images

@router.post("/add", response_model=List[dict])
async def add_path_to_listener(path: str, session: Session = Depends(get_session)):
    result = await process_folder(Path(path), session)
    return result

@router.delete("/remove")
def remove_path_from_listener(path: str, delete_images: bool = False, session: Session = Depends(get_session)):
    path:Path = getFolderPath(path)

    if path is None:
        raise HTTPException(status_code=404, detail="Path not found")
    
    if watcher.fs_watcher.remove(path) == False:
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
            images = session.exec(select(Image).where(Image.directory_id == directory.id))
            for image in images:
                if image.thumbnail_path is not None:
                    (file_api.THUMBNAIL_DIR / image.thumbnail_path).unlink(missing_ok=True)
                session.delete(image)
        session.commit()
    except Exception as e:
        raise HTTPException(status_code=500, detail="Cannot delete images")

@router.get("/listening", response_model=List[Directory])
def get_listening_paths(session: Session = Depends(get_session)):
    directories = session.exec(select(Directory).where(Directory.is_watching == True)).all()
    return directories