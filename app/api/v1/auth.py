from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.db.repositories.user_repo import UserRepository
from app.core.security import verify_password, create_access_token
from app.api.dependencies import get_current_user
from app.db.models.user import User

router = APIRouter(prefix="/auth", tags=["Authentication"])


class UserRegisterRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: Optional[str] = None
    academic_level: str = "Student"


class UserLoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    email: str
    academic_level: str


class UserProfileResponse(BaseModel):
    id: str
    email: str
    full_name: Optional[str] = None
    academic_level: str
    is_active: bool


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(req: UserRegisterRequest, session: AsyncSession = Depends(get_db)):
    repo = UserRepository(session)
    existing = await repo.get_by_email(req.email)
    if existing:
        raise HTTPException(status_code=400, detail="An account with this email already exists.")

    user = await repo.create(
        email=req.email,
        password=req.password,
        full_name=req.full_name,
        academic_level=req.academic_level,
    )
    token = create_access_token(data={"sub": user.id, "email": user.email})
    return TokenResponse(
        access_token=token,
        user_id=user.id,
        email=user.email,
        academic_level=user.academic_level,
    )


@router.post("/login", response_model=TokenResponse)
async def login(req: UserLoginRequest, session: AsyncSession = Depends(get_db)):
    repo = UserRepository(session)
    user = await repo.get_by_email(req.email)
    if not user or not verify_password(req.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    token = create_access_token(data={"sub": user.id, "email": user.email})
    return TokenResponse(
        access_token=token,
        user_id=user.id,
        email=user.email,
        academic_level=user.academic_level,
    )


@router.get("/me", response_model=UserProfileResponse)
async def get_my_profile(current_user: User = Depends(get_current_user)):
    return UserProfileResponse(
        id=current_user.id,
        email=current_user.email,
        full_name=current_user.full_name,
        academic_level=current_user.academic_level,
        is_active=current_user.is_active,
    )
