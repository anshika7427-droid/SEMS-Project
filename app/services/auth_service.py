from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status
import logging
import bcrypt
from app.models import User
from app.schemas import UserCreate, UserLogin

logger = logging.getLogger("auth_service")

class AuthService:
    @staticmethod
    def hash_password(password: str) -> str:
        pwd_bytes = password.encode('utf-8')
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(pwd_bytes, salt)
        return hashed.decode('utf-8')

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        try:
            return bcrypt.checkpw(
                plain_password.encode('utf-8'),
                hashed_password.encode('utf-8')
            )
        except Exception as e:
            logger.error(f"Password verification error: {e}")
            return False

    @classmethod
    async def register(cls, db: AsyncSession, user: UserCreate) -> User:
        result = await db.execute(select(User).where(User.email == user.email))
        existing_user_email = result.scalars().first()

        if existing_user_email:
            logger.warning(f"Registration failed: Email {user.email} already exists.")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already exists"
            )

        result = await db.execute(select(User).where(User.name == user.name))
        existing_user_name = result.scalars().first()

        if existing_user_name:
            logger.warning(f"Registration failed: Username '{user.name}' is already taken.")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already taken"
            )

        new_user = User(
            name=user.name,
            email=user.email,
            password=cls.hash_password(user.password)
        )

        db.add(new_user)
        await db.commit()
        await db.refresh(new_user)
        logger.info(f"User {new_user.email} (ID: {new_user.id}) registered successfully via AuthService.")
        return new_user

    @classmethod
    async def login(cls, db: AsyncSession, credentials: UserLogin, session: dict) -> User:
        result = await db.execute(select(User).where(User.email == credentials.email))
        db_user = result.scalars().first()

        if not db_user or not cls.verify_password(credentials.password, db_user.password):
            logger.warning(f"Failed login attempt for email: {credentials.email}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid credentials"
            )

        # Store user identity in session
        session["user_id"] = db_user.id
        logger.info(f"User {db_user.email} (ID: {db_user.id}) logged in. Session created.")
        return db_user

    @staticmethod
    def logout(session: dict):
        user_id = session.get("user_id")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not logged in."
            )
        session.clear()
        logger.info(f"User with ID {user_id} logged out. Session cleared via AuthService.")

    @staticmethod
    async def validate_session(session: dict, db: AsyncSession) -> User:
        user_id = session.get("user_id")
        logger.info(f"[Auth Audit] Resolving user_id from session: {user_id}")
        
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated. Please log in."
            )
        
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalars().first()
        if not user:
            session.clear()
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Session user not found or deleted."
            )
        
        logger.info(f"[Auth Audit] Successfully authenticated user: {user.email} (ID: {user.id})")
        return user

    @classmethod
    async def get_current_user(cls, session: dict, db: AsyncSession) -> User:
        return await cls.validate_session(session, db)
