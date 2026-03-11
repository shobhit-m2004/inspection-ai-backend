from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from typing import Any

from app.db.session import get_db
from app.models import User
from app.schemas import (
    RegisterRequest,
    RegisterResponse,
    LoginRequest,
    LoginResponse,
    UserResponse,
)
from app.utils.security import hash_password, verify_password, create_access_token
from app.core.exceptions import ConflictException, UnauthorizedException
from app.core.logging_config import get_logger

router = APIRouter(prefix="/auth", tags=["Authentication"])
logger = get_logger(__name__)


@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
    description="Create a new user account with email and password",
    responses={
        400: {"description": "Email already registered"},
    },
)
def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> Any:
    """
    Register a new user account.

    - **name**: User's full name
    - **email**: Valid email address (must be unique)
    - **password**: Password (minimum 8 characters)
    """
    # Check if user already exists
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        logger.warning("Registration attempt with existing email", email=payload.email)
        raise ConflictException(detail="Email already registered")

    # Create new user
    user = User(
        name=payload.name,
        email=payload.email,
        password_hash=hash_password(payload.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    logger.info("New user registered", user_id=user.id, email=user.email)

    # Generate token
    token = create_access_token(str(user.id))

    return LoginResponse(
        token=token,
        token_type="bearer",
        user=UserResponse(
            id=user.id,
            name=user.name,
            email=user.email,
            created_at=user.created_at,
        ),
    )


@router.post(
    "/login",
    response_model=LoginResponse,
    summary="User login",
    description="Authenticate user and return access token",
    responses={
        401: {"description": "Invalid credentials"},
    },
)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> Any:
    """
    Authenticate user and return JWT token.

    - **email**: User's email address
    - **password**: User's password
    """
    user = db.query(User).filter(User.email == payload.email).first()

    if not user or not verify_password(payload.password, user.password_hash):
        logger.warning("Failed login attempt", email=payload.email)
        raise UnauthorizedException(detail="Invalid credentials")

    logger.info("User logged in", user_id=user.id, email=user.email)

    token = create_access_token(str(user.id))

    return LoginResponse(
        token=token,
        token_type="bearer",
        user=UserResponse(
            id=user.id,
            name=user.name,
            email=user.email,
            created_at=user.created_at,
        ),
    )

