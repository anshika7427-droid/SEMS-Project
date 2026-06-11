from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
import logging

from app.database import get_db
from app.models import User
from app.schemas import UserCreate, UserLogin
from app.auth import hash_password, verify_password, get_current_user

router = APIRouter()
logger = logging.getLogger("auth_routes")

# SIGNUP
@router.post("/signup")
def signup(user: UserCreate, db: Session = Depends(get_db)):
    existing_user = db.query(User).filter(
        User.email == user.email
    ).first()

    if existing_user:
        raise HTTPException(
            status_code=400,
            detail="Email already exists"
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
    return {
        "message": "Account created successfully"
    }

# LOGIN
@router.post("/login")
def login(user: UserLogin, request: Request, db: Session = Depends(get_db)):
    db_user = db.query(User).filter(
        User.email == user.email
    ).first()

    if not db_user:
        raise HTTPException(
            status_code=400,
            detail="Invalid email"
        )

    if not verify_password(
        user.password,
        db_user.password
    ):
        raise HTTPException(
            status_code=400,
            detail="Invalid password"
        )

    # Store user identity in session
    request.session["user_id"] = db_user.id
    logger.info(f"User {db_user.email} (ID: {db_user.id}) logged in successfully. Session created.")

    return {
        "message": "Login successful",
        "user_id": db_user.id,
        "name": db_user.name,
        "email": db_user.email
    }

# LOGOUT
@router.post("/logout")
def logout(request: Request):
    user_id = request.session.get("user_id")
    request.session.clear()
    logger.info(f"User with ID {user_id} logged out. Session cleared.")
    return {
        "message": "Logout successful"
    }

# GET CURRENT USER
@router.get("/me")
def get_me(current_user: User = Depends(get_current_user)):
    return {
        "id": current_user.id,
        "name": current_user.name,
        "email": current_user.email
    }