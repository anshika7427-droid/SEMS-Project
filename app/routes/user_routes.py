from fastapi import APIRouter

router = APIRouter()

@router.get("/")
async def users_home():
    return {
        "message": "User route working"
    }