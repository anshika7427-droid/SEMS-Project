from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from fastapi.responses import FileResponse
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

# Ensure upload directory exists outside static mount for security
BASE_DIR = Path(__file__).resolve().parent.parent.parent
UPLOAD_DIR = BASE_DIR / "storage" / "resources"
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
        
    saved_file_name = None
    
    if file:
        filename_str = file.filename or ""
        ext = filename_str.split(".")[-1].lower() if "." in filename_str else ""
        allowed_extensions = {"pdf", "docx", "pptx", "txt"}
        blocked_extensions = {"exe", "bat", "js", "sh"}
        
        if ext in blocked_extensions or (ext and ext not in allowed_extensions):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File type not allowed. Allowed types: {', '.join(allowed_extensions).upper()}"
            )
            
        try:
            # Prevent path traversal by extracting only the basename
            safe_filename = Path(file.filename).name
            filename = f"{current_user.id}_{int(os.urandom(4).hex(), 16)}_{safe_filename}"
            file_path = UPLOAD_DIR / filename
            
            with file_path.open("wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
                
            saved_file_name = filename
            logger.info(f"File uploaded successfully: {file_path}")
        except Exception as e:
            logger.error(f"Failed to save uploaded file: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to save uploaded file"
            )

    new_resource = Resource(
        title=title,
        file_path=saved_file_name,
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
            "file_path": f"/api/resources/download/{r.id}" if r.file_path else None,
            "link": r.link,
            "upload_date": r.upload_date,
            "subject_id": r.subject_id,
            "subject_name": subject.name if subject else "Unknown"
        })
    return result

@router.get("/download/{resource_id}")
def download_resource(
    resource_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    resource = db.query(Resource).filter(
        Resource.id == resource_id,
        Resource.user_id == current_user.id
    ).first()
    
    if not resource or not resource.file_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resource file not found"
        )
        
    file_path = (UPLOAD_DIR / resource.file_path).resolve()
    
    # Path traversal validation check
    if not file_path.exists() or not file_path.is_relative_to(UPLOAD_DIR.resolve()):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied or invalid file path"
        )
        
    # Extract original filename (removing user_id and random hex prefix)
    parts = resource.file_path.split("_", 2)
    original_filename = parts[-1] if len(parts) >= 3 else resource.file_path
    
    return FileResponse(
        path=file_path,
        filename=original_filename,
        media_type="application/octet-stream"
    )

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
        file_path = UPLOAD_DIR / resource.file_path
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