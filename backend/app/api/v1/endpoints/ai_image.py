from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

router = APIRouter()

BACKEND_ROOT = Path(__file__).resolve().parents[4]
IMAGE_DIR = BACKEND_ROOT / "storage" / "netdisk" / "ai_images"

@router.get("/ai_image/{file_name}")
def get_ai_image(file_name: str):
    file_path = IMAGE_DIR / file_name
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="Image not found")
    return FileResponse(str(file_path), media_type="image/png")
