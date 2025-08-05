import os
import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pathlib import Path

from sqlmodel import Session, select

from database.models import Image
from database.database import get_session
from PIL import Image as ImageLoader
from PIL import UnidentifiedImageError
from PIL.ImageFile import ImageFile

router = APIRouter(
    tags=["file"],
)

BASE_DIR = Path("images").resolve()
THUMBBAIL_DIR = BASE_DIR / "thumbnails"
ALLOWED_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.webp'}

def get_unique_filename(folder: Path, ext=".jpg") -> Path | None:
    attempts = 1000
    while attempts > 0:
        attempts -= 1
        name = f"{uuid.uuid4().hex}{ext}"
        path = folder / name
        if not path.exists():
            return path
    return None

def is_image(path: Path) -> bool:
    try:
        with ImageLoader.open(path) as img:
            img.verify()  # Check integrity without decoding pixel data
        return True
    except (UnidentifiedImageError, OSError):
        return False
    
def getPathOfImageFile(file_path: str) -> Path | None:
    image_path = (BASE_DIR / file_path).resolve()
    if (not image_path.is_file() or image_path.suffix.lower() not in ALLOWED_EXTENSIONS):
        return None
    else:
        return image_path

def getFolderPath(path: str | None) -> Path | None:
    if path is None:
        return None
    
    folder = (BASE_DIR / path).resolve()
    if (not folder.is_dir()):
        return None
    else:
        return folder

def create_thumbnail(image: ImageFile, ext: str, size = 256) -> Path:
    if not THUMBBAIL_DIR.exists():
        THUMBBAIL_DIR.mkdir(parents=True, exist_ok=True)

    img = image.copy()
    img.thumbnail((size, size))
    thumbnail_path = get_unique_filename(THUMBBAIL_DIR, ext=ext)
    img.save(thumbnail_path)
    return thumbnail_path

def delete_all_thumbnails():
    for thumbnail in THUMBBAIL_DIR.glob("*"):
        if thumbnail.is_file():
            thumbnail.unlink(missing_ok=True)

@router.get("/thumbnail/init")
def init_thumbnail(session: Session = Depends(get_session)):

    statement = select(Image).where(Image.thumbnail_path == None)
    results = session.exec(statement).all()

    for image in results:
        # Open an image
        pil_image = ImageLoader.open(image.full_path)
        thumbnail_path = create_thumbnail(pil_image, ext=Path(image.full_path).suffix)
        image.thumbnail_path = thumbnail_path.name
    
    session.commit()

    return f'{len(results)} thumbnails created'

@router.get("/thumbnail/delete")
def init_thumbnail(session: Session = Depends(get_session)):
    images = session.exec(select(Image)).all()
    for image in images:
        image.thumbnail_path = None
    session.commit()

    # Remove all thumbnail files
    delete_all_thumbnails()

    return f'{len(images)} thumbnails removed'

@router.get("/file")
def get_image(path: str, session: Session = Depends(get_session)):
    image_path = getPathOfImageFile(path)

    # Ensure it's inside static dir and is a valid image file
    if (image_path is None) or (is_image(image_path) == False):
        raise HTTPException(status_code=404, detail=f"Invalid image: {path}")

    image = session.exec(select(Image).where(Image.full_path == image_path.as_posix())).first()

    if image is None:
        raise HTTPException(status_code=404, detail=f"Image not found: {image_path.as_posix()}")

    return FileResponse(path=image_path)