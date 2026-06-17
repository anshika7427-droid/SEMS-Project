from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.orm import Session
from pathlib import Path
from datetime import date
import logging
import shutil
import os

from app.database import get_db
from app.auth import get_current_user, hash_password, verify_password, User
from app.models import Subject, Milestone, Resource, StudySession
from app.schemas import ProfileUpdate, PasswordChange, ProfileResponse, ProfileUpdateResponse, MessageResponse, AvatarResponse
from app.analytics import get_user_analytics

router = APIRouter()
logger = logging.getLogger("profile_routes")

# Ensure avatar upload directory exists
BASE_DIR = Path(__file__).resolve().parent.parent.parent
AVATAR_DIR = BASE_DIR / "frontend" / "assets" / "avatars"
AVATAR_DIR.mkdir(parents=True, exist_ok=True)

@router.get("/{user_id}", response_model=ProfileResponse)
def get_profile(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to view this profile."
        )
        
    subjects_count = db.query(Subject).filter(Subject.user_id == user_id).count()
    milestones_count = db.query(Milestone).filter(Milestone.user_id == user_id).count()
    resources_count = db.query(Resource).filter(Resource.user_id == user_id).count()
    sessions_count = db.query(StudySession).filter(StudySession.user_id == user_id).count()
    
    analytics = get_user_analytics(user_id, db)
    
    # Generate default join date if not present
    join_date = current_user.created_at
    if not join_date:
        join_date = date.today().strftime("%Y-%m-%d")
        current_user.created_at = join_date
        db.commit()

    return ProfileResponse(
        id=current_user.id,
        name=current_user.name,
        email=current_user.email,
        created_at=join_date,
        avatar_url=current_user.avatar_url or "https://lh3.googleusercontent.com/aida-public/AB6AXuAFcUH75N1o8JqQOcUmxnu2tjKtVBUpyFVyS0a-edF7ah9W2CbtzwbqR-6KzkNr2a5mb3ZWi_skQesjI9T2l5JDZYjQuYfTpCaqN_W62lIJ0Iw8Rii6KBbkHxETFlPJRJpNoYnklX251bxOGvrAi0X_wtWPk7yvf7nER0U_GWaaja1Z0AS3HmE6zRb3qTTU3phLN4NOcEfGG37YYsmUTQLnWAX2OHBrdyikqvQZFdEWtcmqUyfFcajqo2ygXdYFW8qV-rwsEpcItGXV",
        subjects_count=subjects_count,
        milestones_count=milestones_count,
        resources_count=resources_count,
        streak=analytics.get("active_streak", 0),
        study_hours=analytics.get("total_study_hours", 0.0),
        sessions_count=sessions_count
    )

@router.put("/update", response_model=ProfileUpdateResponse)
def update_profile(
    profile: ProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Check if email is already taken by another user
    existing_user = db.query(User).filter(
        User.email == profile.email,
        User.id != current_user.id
    ).first()
    
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email is already in use by another account."
        )
        
    current_user.name = profile.name
    current_user.email = profile.email
    db.commit()
    db.refresh(current_user)
    
    logger.info(f"User profile updated successfully. User ID: {current_user.id}")
    return ProfileUpdateResponse(
        message="Profile updated successfully",
        name=current_user.name,
        email=current_user.email
    )

@router.put("/change-password", response_model=MessageResponse)
def change_password(
    password_data: PasswordChange,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not verify_password(password_data.current_password, current_user.password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect current password."
        )
        
    current_user.password = hash_password(password_data.new_password)
    db.commit()
    
    logger.info(f"User password changed successfully. User ID: {current_user.id}")
    return MessageResponse(message="Password changed successfully")

@router.post("/upload-avatar", response_model=AvatarResponse)
async def upload_avatar(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Sanitize and guard against path traversal in filename
    if ".." in file.filename or "/" in file.filename or "\\" in file.filename:
        logger.warning(f"[Security Alert] Path traversal pattern detected in filename: '{file.filename}' by user {current_user.id}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid filename. Path traversal characters not allowed."
        )

    # Validate file type is image from Content-Type header
    if not file.content_type.startswith("image/"):
        logger.warning(f"Avatar upload failed: invalid content-type '{file.content_type}' for user {current_user.id}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is not an image."
        )
        
    # Validate extension
    ext = Path(file.filename).suffix.lower()
    allowed_extensions = {".png", ".jpg", ".jpeg", ".gif", ".webp"}
    if ext not in allowed_extensions:
        logger.warning(f"Avatar upload failed: disallowed extension '{ext}' for user {current_user.id}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Disallowed file extension. Supported formats: PNG, JPG, JPEG, GIF, WEBP."
        )

    # Validate file size
    try:
        file.file.seek(0, os.SEEK_END)
        file_size = file.file.tell()
        file.file.seek(0)  # Reset pointer to beginning of file
    except Exception as seek_err:
        logger.exception(f"Failed to check file size of uploaded avatar: {seek_err}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not process image file."
        )

    max_size = 5 * 1024 * 1024  # 5 MB
    if file_size > max_size:
        logger.warning(f"Avatar upload failed: File size {file_size} exceeds 5MB limit for user {current_user.id}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File size exceeds the 5MB limit."
        )

    try:
        # Generate safe, unique, random file name to prevent collision/overwrite
        filename = f"avatar_{current_user.id}_{int(os.urandom(4).hex(), 16)}{ext}"
        file_path = AVATAR_DIR / filename
        while file_path.exists():
            filename = f"avatar_{current_user.id}_{int(os.urandom(4).hex(), 16)}{ext}"
            file_path = AVATAR_DIR / filename

        # Delete old avatar file if it exists and is not default
        if current_user.avatar_url:
            old_filename = current_user.avatar_url.split("/")[-1]
            if old_filename != "default_avatar.png":
                old_file_path = AVATAR_DIR / old_filename
                if old_file_path.exists():
                    try:
                        old_file_path.unlink()
                        logger.info(f"Deleted old avatar file: {old_file_path}")
                    except Exception as unlink_err:
                        logger.exception(f"Error deleting old avatar file: {unlink_err}")

        # Save new avatar to destination
        with file_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        avatar_url = f"/static/assets/avatars/{filename}"
        current_user.avatar_url = avatar_url
        db.commit()
        
        logger.info(f"Avatar uploaded successfully for user {current_user.id}: {avatar_url}")
        return AvatarResponse(
            message="Avatar uploaded successfully",
            avatar_url=avatar_url
        )
    except Exception as e:
        logger.exception(f"Avatar upload failed due to server error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload avatar"
        )
