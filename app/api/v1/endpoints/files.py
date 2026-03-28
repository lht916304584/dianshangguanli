import os
import uuid
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.api.deps import CurrentUser

router = APIRouter()

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

ALLOWED_CONTENT_TYPES = {
    "image/jpeg", "image/png", "image/webp", "image/gif",
    "application/pdf",
    "text/csv",
}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


class UploadResponse(BaseModel):
    file_id: str
    filename: str
    content_type: str
    size: int
    url: str


@router.post("/upload", response_model=UploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_file(
    current_user: CurrentUser,
    file: UploadFile = File(...),
):
    """Upload a single file (max 10 MB). Returns a file_id for later retrieval."""
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported file type: {file.content_type}",
        )

    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File exceeds 10 MB limit",
        )

    ext = Path(file.filename).suffix.lower()
    file_id = str(uuid.uuid4())
    dest = UPLOAD_DIR / f"{file_id}{ext}"

    dest.write_bytes(contents)

    return UploadResponse(
        file_id=file_id,
        filename=file.filename,
        content_type=file.content_type,
        size=len(contents),
        url=f"/api/v1/files/{file_id}",
    )


@router.get("/{file_id}")
async def get_file(file_id: str, current_user: CurrentUser):
    """Download a previously uploaded file by its file_id."""
    # Sanitize: only allow UUID-like names
    try:
        uuid.UUID(file_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid file_id")

    matches = list(UPLOAD_DIR.glob(f"{file_id}.*"))
    if not matches:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")

    return FileResponse(matches[0])


@router.delete("/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_file(file_id: str, current_user: CurrentUser):
    """Delete an uploaded file."""
    try:
        uuid.UUID(file_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid file_id")

    matches = list(UPLOAD_DIR.glob(f"{file_id}.*"))
    if not matches:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")

    matches[0].unlink()
