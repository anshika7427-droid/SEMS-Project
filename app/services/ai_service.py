from sqlalchemy.ext.asyncio import AsyncSession
from app.ai_engine import get_ai_recommendations

class AIService:
    @staticmethod
    async def get_recommendations_for_user(db: AsyncSession, user_id: int) -> dict:
        """Fetch AI recommendations and study guidance for the user."""
        return await get_ai_recommendations(user_id, db)
