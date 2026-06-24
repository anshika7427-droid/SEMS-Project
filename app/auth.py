from fastapi import Request, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models import User
from app.services.auth_service import AuthService

def hash_password(password: str) -> str:
    return AuthService.hash_password(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return AuthService.verify_password(plain_password, hashed_password)

async def get_current_user(request: Request, db: AsyncSession = Depends(get_db)) -> User:
    return await AuthService.get_current_user(request.session, db)