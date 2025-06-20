from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pathlib import Path

router = APIRouter(
    tags=["vector_db"],
)

BASE_DIR = Path("images").resolve()
ALLOWED_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.webp'}

@router.get("/image")
def get_image(name: str):
    image_path = (BASE_DIR / name).resolve()

    # Ensure it's inside static dir and is a valid image file
    if (
        not image_path.is_file() or
        image_path.suffix.lower() not in ALLOWED_EXTENSIONS
    ):
        raise HTTPException(status_code=404, detail="Invalid image path")

    return FileResponse(path=image_path)