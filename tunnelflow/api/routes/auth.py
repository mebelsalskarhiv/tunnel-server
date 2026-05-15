"""
TunnelFlow Authentication API Routes
User registration, login, JWT token management
"""

from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
import jwt
import hashlib
import secrets

from tunnelflow.db.database import get_db
from tunnelflow.db.models import User
from tunnelflow.billing.plans import initialize_plans, get_user_plan, get_user_limits, get_current_usage

router = APIRouter(prefix="/auth", tags=["Authentication"])

# Конфигурация JWT
JWT_SECRET = secrets.token_urlsafe(32)  # В продакшене хранить в .env
JWT_ALGORITHM = "HS256"
TOKEN_EXPIRE_DAYS = 30

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")


# Pydantic модели
class UserRegister(BaseModel):
    email: EmailStr
    password: str


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class UserResponse(BaseModel):
    id: int
    email: str
    current_plan: str
    created_at: datetime
    is_active: bool


class UserProfileResponse(UserResponse):
    plan_details: dict
    usage: dict
    limits: dict


def hash_password(password: str) -> str:
    """Хэширование пароля"""
    salt = secrets.token_hex(16)
    salted = f"{salt}:{password}"
    password_hash = hashlib.sha256(salted.encode()).hexdigest()
    return f"{salt}:{password_hash}"


def verify_password(password: str, password_hash: str) -> bool:
    """Проверка пароля"""
    try:
        salt, stored_hash = password_hash.split(":")
        salted = f"{salt}:{password}"
        computed_hash = hashlib.sha256(salted.encode()).hexdigest()
        return computed_hash == stored_hash
    except (ValueError, AttributeError):
        return False


def create_jwt_token(user_id: int, email: str) -> str:
    """Создать JWT токен"""
    expire = datetime.utcnow() + timedelta(days=TOKEN_EXPIRE_DAYS)
    payload = {
        "user_id": user_id,
        "email": email,
        "exp": expire,
        "iat": datetime.utcnow(),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_jwt_token(token: str) -> Optional[dict]:
    """Декодировать JWT токен"""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> User:
    """Получить текущего пользователя из токена"""
    payload = decode_jwt_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user_id = payload.get("user_id")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user = db.query(User).filter(User.id == user_id).first()
    if user is None or not user.is_active or user.is_blocked:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or blocked",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return user


@router.post("/register", response_model=UserResponse, status_code=201)
def register(user_data: UserRegister, db: Session = Depends(get_db)):
    """Регистрация нового пользователя"""
    # Проверка существующего email
    existing = db.query(User).filter(User.email == user_data.email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )
    
    # Создаем пользователя
    user = User(
        email=user_data.email,
        password_hash=hash_password(user_data.password),
        current_plan="free",
        is_active=True,
    )
    
    db.add(user)
    db.commit()
    db.refresh(user)
    
    # Инициализируем тарифные планы если нужно
    initialize_plans(db)
    
    return user


@router.post("/login", response_model=TokenResponse)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """Вход пользователя"""
    user = db.query(User).filter(User.email == form_data.username).first()
    
    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated",
        )
    
    if user.is_blocked:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Account is blocked: {user.blocked_reason}",
        )
    
    token = create_jwt_token(user.id, user.email)
    
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
    )


@router.get("/me", response_model=UserProfileResponse)
def get_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Получить профиль текущего пользователя"""
    plan = get_user_plan(db, current_user.id)
    limits = get_user_limits(db, current_user.id)
    usage = get_current_usage(db, current_user.id)
    
    return UserProfileResponse(
        id=current_user.id,
        email=current_user.email,
        current_plan=current_user.current_plan.value,
        created_at=current_user.created_at,
        is_active=current_user.is_active,
        plan_details={
            "name": plan.name if plan else "unknown",
            "price_usd": plan.price_usd if plan else 0,
            "plan_expires_at": current_user.plan_expires_at,
        },
        usage=usage,
        limits=limits,
    )


@router.put("/me/password")
def change_password(
    old_password: str,
    new_password: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Смена пароля"""
    if not verify_password(old_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect current password",
        )
    
    current_user.password_hash = hash_password(new_password)
    db.commit()
    
    return {"message": "Password changed successfully"}
