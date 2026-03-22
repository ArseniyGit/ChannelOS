from pathlib import Path
import uuid

import logging
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from .dependencies import require_telegram_user_data

router = APIRouter()
logger = logging.getLogger(__name__)

UPLOAD_DIR = Path(__file__).parent.parent.parent / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
MAX_FILE_SIZE = 10 * 1024 * 1024


@router.post("/upload-image")
async def upload_image(
    file: UploadFile = File(...),
    user_data: dict = Depends(require_telegram_user_data),
):
    """Загрузить изображение для рекламы"""

    file_extension = Path(file.filename).suffix.lower()
    if file_extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Неподдерживаемый формат файла. Разрешены: {', '.join(ALLOWED_EXTENSIONS)}"
        )

    contents = await file.read()
    file_size = len(contents)

    if file_size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Файл слишком большой. Максимум: 10 MB"
        )

    unique_filename = f"{uuid.uuid4()}{file_extension}"
    file_path = UPLOAD_DIR / unique_filename

    try:
        with open(file_path, "wb") as f:
            f.write(contents)

        logger.info(f"Image uploaded: {unique_filename} ({file_size} bytes) by user {user_data['telegram_id']}")

        file_url = f"/uploads/{unique_filename}"

        return {
            "success": True,
            "url": file_url,
            "filename": unique_filename,
            "size": file_size
        }

    except Exception as e:
        logger.exception(f"Error saving file: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка при сохранении файла"
        )
