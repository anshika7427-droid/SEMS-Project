from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.orm import Session
from pathlib import Path
from datetime import date
import logging
import shutil
import os

from app.database import get_db
from app.auth import get_current_user, User
from app.models import Resource, Subject

router = APIRouter()
logger = logging.getLogger("resource_routes")

# Ensure upload directory exists
BASE_DIR = Path(__file__).resolve().parent.parent.parent
UPLOAD_DIR = BASE_DIR / "frontend" / "assets" / "resources"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

@router.get("/")
async def resource_home():
    return {
        "message": "Resource route working"
    }

@router.post("/upload")
async def upload_resource(
    title: str = Form(...),
    subject_id: int = Form(...),
    link: str = Form(None),
    file: UploadFile = File(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Verify subject belongs to user
    subject = db.query(Subject).filter(
        Subject.id == subject_id,
        Subject.user_id == current_user.id
    ).first()
    
    if not subject:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Subject not found or does not belong to the user"
        )
        
    saved_file_path = None
    
    if file:
        try:
            # Generate safe file name
            filename = f"{current_user.id}_{int(os.urandom(4).hex(), 16)}_{file.filename}"
            file_path = UPLOAD_DIR / filename
            
            with file_path.open("wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
                
            saved_file_path = f"/static/assets/resources/{filename}" # Accessible URL via static files mount
            logger.info(f"File uploaded successfully: {file_path}")
        except Exception as e:
            logger.error(f"Failed to save uploaded file: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to save uploaded file"
            )

    new_resource = Resource(
        title=title,
        file_path=saved_file_path,
        link=link if link else None,
        upload_date=date.today().strftime("%Y-%m-%d"),
        subject_id=subject_id,
        user_id=current_user.id
    )
    
    db.add(new_resource)
    db.commit()
    db.refresh(new_resource)
    
    logger.info(f"Resource created in DB. ID: {new_resource.id}, User ID: {current_user.id}")
    return {
        "message": "Resource uploaded successfully",
        "resource_id": new_resource.id
    }

@router.get("/all")
def get_resources(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    resources = db.query(Resource).filter(Resource.user_id == current_user.id).all()
    result = []
    for r in resources:
        subject = db.query(Subject).filter(Subject.id == r.subject_id).first()
        result.append({
            "id": r.id,
            "title": r.title,
            "file_path": r.file_path,
            "link": r.link,
            "upload_date": r.upload_date,
            "subject_id": r.subject_id,
            "subject_name": subject.name if subject else "Unknown"
        })
    return result

@router.delete("/{resource_id}")
def delete_resource(
    resource_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    resource = db.query(Resource).filter(Resource.id == resource_id).first()
    if not resource:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resource not found"
        )
    if resource.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Unauthorized access to this resource"
        )
        
    # Delete file from filesystem if it exists
    if resource.file_path:
        filename = resource.file_path.split("/")[-1]
        file_path = UPLOAD_DIR / filename
        if file_path.exists():
            try:
                file_path.unlink()
                logger.info(f"Deleted file from filesystem: {file_path}")
            except Exception as e:
                logger.error(f"Error deleting file {file_path}: {e}")
                
    db.delete(resource)
    db.commit()
    logger.info(f"Resource ID {resource_id} deleted successfully by user {current_user.id}")
    return {"message": "Resource deleted successfully"}