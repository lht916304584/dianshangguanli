from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentUser, DBSession
from app.core.security import create_access_token, create_refresh_token, decode_token
from app.schemas.user import LoginRequest, MessageResponse, RefreshRequest, Token, UserRead
from app.services.user_service import UserService

router = APIRouter()


@router.post("/login", response_model=Token)
async def login(payload: LoginRequest, db: DBSession):
    """Authenticate and receive JWT tokens."""
    user_service = UserService(db)
    user = await user_service.authenticate(payload.email, payload.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Inactive user")

    return Token(
        access_token=create_access_token(str(user.id)),
        refresh_token=create_refresh_token(str(user.id)),
    )


@router.post("/refresh", response_model=Token)
async def refresh_tokens(payload: RefreshRequest, db: DBSession):
    """Exchange a valid refresh token for new token pair."""
    from jose import JWTError

    try:
        token_data = decode_token(payload.refresh_token)
        if token_data.get("type") != "refresh":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    user_service = UserService(db)
    user = await user_service.get_by_id(token_data["sub"])
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")

    return Token(
        access_token=create_access_token(str(user.id)),
        refresh_token=create_refresh_token(str(user.id)),
    )


@router.get("/me", response_model=UserRead)
async def get_me(current_user: CurrentUser):
    """Return the authenticated user's profile."""
    return current_user


@router.post("/logout", response_model=MessageResponse)
async def logout(current_user: CurrentUser):
    """Stateless logout — client should discard tokens."""
    # For stateful invalidation, add token to Redis blacklist here
    return MessageResponse(message="Successfully logged out")
