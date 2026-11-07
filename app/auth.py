import re
import os
from datetime import datetime, timedelta
from typing import Optional
import jwt
import bcrypt
from fastapi import Request, Depends, HTTPException, status
from sqlalchemy.orm import Session
from .database import get_db
from .models import User

SECRET_KEY = os.getenv("SECRET_KEY", "sampark-super-secure-secret-key-change-in-prod-2026")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_DAYS = 30

def clean_vehicle_number(raw_str: str) -> str:
    """
    Cleans vehicle number: uppercase, removes all whitespace and special characters like hyphens/dots.
    e.g. 'dl-01 ab 1234' -> 'DL01AB1234'
    """
    if not raw_str:
        return ""
    return re.sub(r"[^A-Za-z0-9]", "", raw_str).upper()

def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except Exception:
        return False

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(days=ACCESS_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def get_current_user(request: Request, db: Session = Depends(get_db)) -> Optional[User]:
    """
    Retrieves user from cookie or returns None if unauthenticated.
    """
    token = request.cookies.get("sampark_token")
    if not token:
        # Check Authorization header as fallback
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]

    if not token:
        return None

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: int = payload.get("user_id")
        if user_id is None:
            return None
        return db.query(User).filter(User.id == user_id).first()
    except Exception:
        return None

def require_login(request: Request, db: Session = Depends(get_db)) -> User:
    user = get_current_user(request, db)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_303_SEE_OTHER,
            headers={"Location": "/login?error=Please+login+first"}
        )
    return user

