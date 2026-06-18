from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
import logging

from app.database import get_db
from app.models import User
from app.schemas import UserCreate, UserLogin, MessageResponse, LoginResponse, AuthStatusResponse
from app.auth import get_current_user
from app.services.auth_service import AuthService
from app.utils.limiter import limiter

router = APIRouter()
logger = logging.getLogger("auth_routes")

# SIGNUP / REGISTER
@router.post("/register", response_model=MessageResponse)
@router.post("/signup", response_model=MessageResponse)
@limiter.limit("5/minute")
def register(request: Request, user: UserCreate, db: Session = Depends(get_db)):
    AuthService.register(db, user)
    return MessageResponse(
        message="Account created successfully"
    )

# LOGIN
@router.post("/login", response_model=LoginResponse)
@limiter.limit("5/minute")
def login(request: Request, user: UserLogin, db: Session = Depends(get_db)):
    db_user = AuthService.login(db, user, request.session)
    return LoginResponse(
        message="Login successful",
        user_id=db_user.id,
        name=db_user.name,
        email=db_user.email
    )

# LOGOUT
@router.post("/logout", response_model=MessageResponse)
def logout(request: Request):
    AuthService.logout(request.session)
    return MessageResponse(
        message="Logout successful"
    )

# GET CURRENT USER / STATUS
@router.get("/status", response_model=AuthStatusResponse)
@router.get("/me", response_model=AuthStatusResponse)
def get_status(current_user: User = Depends(get_current_user)):
    return AuthStatusResponse(
        id=current_user.id,
        name=current_user.name,
        email=current_user.email
    )