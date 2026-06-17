from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
import logging

from app.database import get_db
from app.models import User
from app.schemas import UserCreate, UserLogin, MessageResponse, LoginResponse, AuthStatusResponse
from app.auth import hash_password, verify_password, get_current_user

router = APIRouter()
logger = logging.getLogger("auth_routes")

# SIGNUP
@router.post("/signup", response_model=MessageResponse)
def signup(user: UserCreate, db: Session = Depends(get_db)):
    existing_user_email = db.query(User).filter(
        User.email == user.email
    ).first()

    if existing_user_email:
        logger.warning(f"Registration failed: Email {user.email} already exists.")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already exists"
        )

    existing_user_name = db.query(User).filter(
        User.name == user.name
    ).first()

    if existing_user_name:
        logger.warning(f"Registration failed: Username '{user.name}' is already taken.")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already taken"
        )

    new_user = User(
        name=user.name,
        email=user.email,
        password=hash_password(user.password)
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    logger.info(f"User {new_user.email} (ID: {new_user.id}) signed up successfully.")
    return MessageResponse(
        message="Account created successfully"
    )

# LOGIN
@router.post("/login", response_model=LoginResponse)
def login(user: UserLogin, request: Request, db: Session = Depends(get_db)):
    db_user = db.query(User).filter(
        User.email == user.email
    ).first()

    if not db_user or not verify_password(user.password, db_user.password):
        logger.warning(f"Failed login attempt for email: {user.email}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid credentials"
        )

    # Store user identity in session
    request.session["user_id"] = db_user.id
    logger.info(f"User {db_user.email} (ID: {db_user.id}) logged in successfully. Session created.")

    return LoginResponse(
        message="Login successful",
        user_id=db_user.id,
        name=db_user.name,
        email=db_user.email
    )

# LOGOUT
@router.post("/logout", response_model=MessageResponse)
def logout(request: Request):
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not logged in."
        )
    request.session.clear()
    logger.info(f"User with ID {user_id} logged out. Session cleared.")
    return MessageResponse(
        message="Logout successful"
    )

# GET CURRENT USER
@router.get("/me", response_model=AuthStatusResponse)
def get_me(current_user: User = Depends(get_current_user)):
    return AuthStatusResponse(
        id=current_user.id,
        name=current_user.name,
        email=current_user.email
    )