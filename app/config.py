import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY", "sems-secret-key-change-me-in-production")
LLM_API_KEY = os.getenv("LLM_API_KEY")
LLM_MODEL = os.getenv("LLM_MODEL", "llama-3.3-70b")
LLM_API_URL = os.getenv("LLM_API_URL", "https://api.groq.com/openai/v1")

