from sqlalchemy.orm import Session
from app.ai_engine import get_ai_recommendations

class AIService:
    @staticmethod
    def get_recommendations_for_user(db: Session, user_id: int) -> dict:
        """Fetch AI recommendations and study guidance for the user."""
        return get_ai_recommendations(user_id, db)
