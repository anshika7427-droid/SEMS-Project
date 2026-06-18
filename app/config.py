import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY or SECRET_KEY == "sems-secret-key-change-me-in-production":
    raise ValueError("SECRET_KEY must be configured and cannot be the insecure default value.")
LLM_API_KEY = os.getenv("LLM_API_KEY")
LLM_MODEL = os.getenv("LLM_MODEL", "llama-3.3-70b")
LLM_API_URL = os.getenv("LLM_API_URL", "https://api.groq.com/openai/v1")
CORS_ORIGINS = [orig.strip() for orig in os.getenv("CORS_ORIGINS", "http://127.0.0.1:8000,http://localhost:8000").split(",") if orig.strip()]

