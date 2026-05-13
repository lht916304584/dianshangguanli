"""文件上传/下载/删除 API（已修复文件归属校验漏洞）"""

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


def _user_file_dir(user_id: str) -> Path:
    """每个用户独立子目录，物理隔离文件。"""
    d = UPLOAD_DIR / str(user_id)
    d.mkdir(parents=True, exist_ok=True)
    return d


def _find_user_file(user_id: str, file_id: str) -> Path:
    """在当前用户目录下查找文件，找不到则抛 404。"""
    try:
        uuid.UUID(file_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid file_id")

    user_dir = _user_file_dir(str(user_id))
    matches = list(user_dir.glob(f"{file_id}.*"))
    if not matches:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")
    return matches[0]


@router.post("/upload", response_model=UploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_file(
    current_user: CurrentUser,
    file: UploadFile = File(...),
):
    """上传单个文件（最大 10 MB），返回 file_id 供后续访问。"""
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
    user_dir = _user_file_dir(str(current_user.id))
    dest = user_dir / f"{file_id}{ext}"
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
    """下载文件（只能访问自己上传的文件）。"""
    file_path = _find_user_file(current_user.id, file_id)
    return FileResponse(file_path)


@router.delete("/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_file(file_id: str, current_user: CurrentUser):
    """删除文件（只能删除自己上传的文件）。"""
    file_path = _find_user_file(current_user.id, file_id)
    file_path.unlink()
