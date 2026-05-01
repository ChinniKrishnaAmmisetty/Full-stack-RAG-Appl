"""Authentication endpoints: register, login, and current-user info."""

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, or_, select
from slowapi import Limiter
from slowapi.util import get_remote_address
from app.database import get_db
from app.models import User
from app.schemas import UserRegister, UserLogin, Token, UserResponse, ForgotPasswordRequest, ResetPasswordRequest
from app.auth import hash_password, verify_password, create_access_token, get_current_user, decode_access_token
import logging

logger = logging.getLogger(__name__)

# Rate limiter for auth endpoints
limiter = Limiter(key_func=get_remote_address)

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=Token, status_code=status.HTTP_201_CREATED)
@limiter.limit("3/minute")
async def register(request: Request, data: UserRegister, db: AsyncSession = Depends(get_db)):
    """Register a new user account."""
    username = data.username.strip()
    email = data.email.strip().lower()
    logger.info("Register request | username=%s | email=%s", username, email)
    # Check if email already exists
    result = await db.execute(select(User).where(func.lower(User.email) == email))
    if result.scalar_one_or_none():
        logger.warning("Registration blocked | email already registered | email=%s", email)
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    # Check if username already exists
    result = await db.execute(select(User).where(func.lower(User.username) == username.lower()))
    if result.scalar_one_or_none():
        logger.warning("Registration blocked | username already taken | username=%s", username)
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username already taken")

    # Create user
    user = User(
        email=email,
        username=username,
        hashed_password=hash_password(data.password),
    )
    db.add(user)
    await db.flush()
    logger.info("Registration succeeded | user_id=%s | username=%s", user.id, user.username)

    token = create_access_token(data={"sub": user.id})
    return Token(access_token=token)


@router.post("/login", response_model=Token)
@limiter.limit("5/minute")
async def login(request: Request, data: UserLogin, db: AsyncSession = Depends(get_db)):
    """Authenticate with username/email + password and receive a JWT token."""
    identifier = data.username.strip()
    normalized_identifier = identifier.lower()
    logger.info("Login request | identifier=%s", identifier)
    result = await db.execute(
        select(User).where(
            or_(
                func.lower(User.username) == normalized_identifier,
                func.lower(User.email) == normalized_identifier,
            )
        )
    )
    user = result.scalar_one_or_none()

    if not user:
        logger.warning("Login failed | user not found | identifier=%s", identifier)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username/email or password",
        )
        
    if not verify_password(data.password, user.hashed_password):
        logger.warning("Login failed | bad password | user_id=%s | username=%s", user.id, user.username)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username/email or password",
        )

    token = create_access_token(data={"sub": user.id})
    logger.info("Login succeeded | user_id=%s | username=%s", user.id, user.username)
    return Token(access_token=token)


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    """Get the currently authenticated user's info."""
    return current_user


@router.post("/forgot-password")
@limiter.limit("3/minute")
async def forgot_password(request: Request, data: ForgotPasswordRequest, db: AsyncSession = Depends(get_db)):
    """Generate a password reset token for the given email."""
    result = await db.execute(select(User).where(User.email == data.email))
    user = result.scalar_one_or_none()
    
    if not user:
        # Don't reveal if user exists or not for security, though this is dev mode
        return {"message": "If an account with that email exists, a password reset token has been generated.", "reset_token": None}
        
    # Generate a short-lived token (e.g. 15 minutes) for resetting
    from datetime import timedelta
    token = create_access_token(data={"sub": user.id, "type": "reset"}, expires_delta=timedelta(minutes=15))
    
    # In a real app, send an email here. For dev, we return it to the frontend to mock the flow.
    return {
        "message": "Password reset token generated (mock email sent)",
        "reset_token": token
    }


@router.post("/reset-password")
@limiter.limit("3/minute")
async def reset_password(request: Request, data: ResetPasswordRequest, db: AsyncSession = Depends(get_db)):
    """Reset the password using a valid token."""
    try:
        payload = decode_access_token(data.token)
        if payload.get("type") != "reset":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid token type")
            
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid token")
            
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
            
        user.hashed_password = hash_password(data.new_password)
        db.add(user)
        await db.flush() # or commit if not handled by middleware
        
        return {"message": "Password updated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error resetting password: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired reset token")
