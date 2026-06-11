from fastapi import APIRouter

router = APIRouter()

@router.get("/")
async def schedule_home():
    return {
        "message": "Schedule route working"
    }