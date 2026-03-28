import uuid

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import CurrentSuperuser, CurrentUser, DBSession
from app.schemas.user import MessageResponse, PaginatedResponse, UserCreate, UserRead, UserUpdate
from app.services.user_service import UserService

router = APIRouter()


@router.get("/", response_model=PaginatedResponse)
async def list_users(
    db: DBSession,
    _: CurrentSuperuser,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
):
    """List all users (superuser only)."""
    user_service = UserService(db)
    users, total = await user_service.list_users(skip=(page - 1) * size, limit=size)
    return PaginatedResponse(
        total=total,
        page=page,
        size=size,
        items=[UserRead.model_validate(u) for u in users],
    )


@router.post("/", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def create_user(payload: UserCreate, db: DBSession):
    """Register a new user (public endpoint)."""
    user_service = UserService(db)
    existing = await user_service.get_by_email(payload.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )
    user = await user_service.create(payload)
    return user


@router.get("/me", response_model=UserRead)
async def read_me(current_user: CurrentUser):
    return current_user


@router.patch("/me", response_model=UserRead)
async def update_me(payload: UserUpdate, current_user: CurrentUser, db: DBSession):
    user_service = UserService(db)
    updated = await user_service.update(current_user, payload)
    return updated


@router.get("/{user_id}", response_model=UserRead)
async def get_user(user_id: uuid.UUID, db: DBSession, _: CurrentSuperuser):
    user_service = UserService(db)
    user = await user_service.get_by_id(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


@router.delete("/{user_id}", response_model=MessageResponse)
async def delete_user(user_id: uuid.UUID, db: DBSession, _: CurrentSuperuser):
    user_service = UserService(db)
    user = await user_service.get_by_id(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    await user_service.delete(user)
    return MessageResponse(message="User deleted")
