from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pathlib import Path

router = APIRouter(
    tags=["file"],
)

BASE_DIR = Path("images").resolve()
ALLOWED_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.webp'}

def getImageFile(file_path: str) -> Path | None:
    image_path = (BASE_DIR / file_path).resolve()
    if (not image_path.is_file() or image_path.suffix.lower() not in ALLOWED_EXTENSIONS):
        return None
    else:
        return image_path

def getFolder(path: str | None) -> Path | None:
    if path is None:
        return None
    
    folder = (BASE_DIR / path).resolve()
    if (not folder.is_dir()):
        return None
    else:
        return folder
    
@router.get("/file")
def get_image(path: str):
    image_path = getImageFile(path)

    # Ensure it's inside static dir and is a valid image file
    if image_path is None:
        raise HTTPException(status_code=404, detail="Invalid image path")

    return FileResponse(path=image_path)