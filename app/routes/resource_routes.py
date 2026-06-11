from fastapi import APIRouter

router = APIRouter()

@router.get("/")
async def resource_home():
    return {
        "message": "Resource route working"
    }