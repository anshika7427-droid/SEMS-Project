from fastapi import Request, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User
from app.services.auth_service import AuthService

def hash_password(password: str) -> str:
    return AuthService.hash_password(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return AuthService.verify_password(plain_password, hashed_password)

def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    return AuthService.get_current_user(request.session, db)