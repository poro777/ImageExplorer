from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pathlib import Path

from sqlmodel import Session, select

from database.models import Image
from database.database import get_session

router = APIRouter(
    tags=["file"],
)

BASE_DIR = Path("images").resolve()
ALLOWED_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.webp'}

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
    
@router.get("/file")
def get_image(path: str, session: Session = Depends(get_session)):
    image_path = getPathOfImageFile(path)

    # Ensure it's inside static dir and is a valid image file
    if image_path is None:
        raise HTTPException(status_code=404, detail="Invalid image path")

    image = session.exec(select(Image).where(Image.full_path == image_path.as_posix())).first()

    if image is None:
        raise HTTPException(status_code=404, detail="Image not found")

    return FileResponse(path=image_path)