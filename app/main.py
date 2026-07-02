from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, RedirectResponse
from starlette.middleware.sessions import SessionMiddleware
from pathlib import Path
from contextlib import asynccontextmanager
import asyncio
import sys
import os
import logging
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from app.utils.limiter import limiter
from alembic.config import Config
from alembic import command

# -----------------------------------
# IMPORT DATABASE
# -----------------------------------

from app.database import engine
from app.models import Base
from app.config import SECRET_KEY, CORS_ORIGINS, LLM_API_KEY

# -----------------------------------
# IMPORT ROUTES
# -----------------------------------

from app.routes.auth_routes import router as auth_router
from app.routes.user_routes import router as user_router
from app.routes.task_routes import router as task_router
from app.routes.analytics_routes import router as analytics_router
from app.routes.resource_routes import router as resource_router
from app.routes.schedule_routes import router as schedule_router
from app.routes.subject_routes import router as subject_router
from app.routes import milestone_routes
from app.routes.profile_routes import router as profile_router
from app.routes.notification_routes import router as notification_router
from app.routes.study_session_routes import router as study_session_router

# -----------------------------------
# CREATE DATABASE TABLES
# -----------------------------------

# Table creation and migrations are managed by Alembic.

logger = logging.getLogger("main")

@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        logger.info("Running database migrations via Alembic...")
        base_dir = Path(__file__).resolve().parent.parent
        alembic_cfg = Config(str(base_dir / "alembic.ini"))
        await asyncio.to_thread(command.upgrade, alembic_cfg, "head")
        logger.info("Database migrations applied successfully.")
    except Exception as e:
        logger.error(f"Error applying database migrations during startup: {e}")

    if not LLM_API_KEY:
        logger.warning("WARNING: LLM_API_KEY environment variable is not configured. AI schedule generation will fail.")
    yield

app = FastAPI(
    title="AI-Based Education Recommendation System",
    description="Modern AI Student Productivity Platform",
    version="1.0.0",
    lifespan=lifespan
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

import re
from starlette_csrf import CSRFMiddleware

class AppCSRFMiddleware(CSRFMiddleware):
    async def __call__(self, scope, receive, send) -> None:
        if "pytest" in sys.modules or os.getenv("TESTING") == "True":
            await self.app(scope, receive, send)
            return
        await super().__call__(scope, receive, send)

is_testing = "pytest" in sys.modules or os.getenv("TESTING") == "True"

# RECOMMENDATION: For enhanced production security, implement CSRF protection (e.g., using asgi-csrf middleware or double-submit cookie patterns) to safeguard session-based requests.
app.add_middleware(
    SessionMiddleware,
    secret_key=SECRET_KEY,
    session_cookie="session",
    max_age=14 * 24 * 3600,  # 14 days
    same_site="lax",
    https_only=not is_testing
)

app.add_middleware(
    AppCSRFMiddleware,
    secret=SECRET_KEY,
    required_urls=[re.compile(r"^/api/(auth|tasks|subjects|milestones|resources|schedule|profile|notifications)/.*")],
    exempt_urls=[re.compile(r"^/api/auth/login$"), re.compile(r"^/api/auth/register$"), re.compile(r"^/api/auth/signup$")],
    cookie_name="csrftoken",
    header_name="X-CSRFToken",
)

# -----------------------------------
# CORS CONFIG
# -----------------------------------

# Using specific allowed origins rather than "*" to support credentials (session cookies)
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -----------------------------------
# BASE DIRECTORY
# -----------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent

# -----------------------------------
# FRONTEND PATH
# -----------------------------------

frontend_path = BASE_DIR / "frontend"

# -----------------------------------
# STATIC FILES
# -----------------------------------

app.mount(
    "/static",
    StaticFiles(directory=frontend_path),
    name="static"
)

# Mount avatar uploads directory outside frontend directory
avatar_storage_path = BASE_DIR / "storage" / "avatars"
avatar_storage_path.mkdir(parents=True, exist_ok=True)
app.mount(
    "/uploads/avatars",
    StaticFiles(directory=avatar_storage_path),
    name="avatars"
)

# -----------------------------------
# LANDING PAGE ROUTE
# -----------------------------------

@app.get("/")
async def landing_page():
    return FileResponse(
        frontend_path / "pages" / "index.html"
    )

# -----------------------------------
# DASHBOARD ROUTE (PROTECTED)
# -----------------------------------

@app.get("/dashboard")
async def dashboard(request: Request):
    if not request.session.get("user_id"):
        return RedirectResponse(url="/")
    return FileResponse(
        frontend_path / "pages" / "dashboard.html"
    )

# -----------------------------------
# SMART SCHEDULER ROUTE (PROTECTED)
# -----------------------------------

@app.get("/smart_scheduler")
def smart_scheduler(request: Request):
    if not request.session.get("user_id"):
        return RedirectResponse(url="/")
    return FileResponse(
        frontend_path / "pages" / "smart_scheduler.html"
    )

# -----------------------------------
# RESOURCES ROUTE (PROTECTED)
# -----------------------------------

@app.get("/resources")
def resources_page(request: Request):
    if not request.session.get("user_id"):
        return RedirectResponse(url="/")
    return FileResponse(
        frontend_path / "pages" / "resources.html"
    )

# -----------------------------------
# PROFILE ROUTE (PROTECTED)
# -----------------------------------

@app.get("/profile")
def profile_page(request: Request):
    if not request.session.get("user_id"):
        return RedirectResponse(url="/")
    return FileResponse(
        frontend_path / "pages" / "profile.html"
    )

# -----------------------------------
# OPTIONAL PAGES
# -----------------------------------

@app.get("/about")
async def about_page():
    return FileResponse(
        frontend_path / "pages" / "about.html"
    )

@app.get("/features")
async def features_page():
    return FileResponse(
        frontend_path / "pages" / "features.html"
    )

@app.get("/contact")
async def contact_page():
    return FileResponse(
        frontend_path / "pages" / "contact.html"
    )

# -----------------------------------
# API TEST ROUTE
# -----------------------------------

@app.get("/api")
async def api_test():
    return {
        "message": "FastAPI backend running successfully"
    }

# -----------------------------------
# HEALTH CHECK
# -----------------------------------

@app.get("/health")
async def health_check():
    db_connected = False
    try:
        from sqlalchemy import text
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        db_connected = True
    except Exception as e:
        logger.error(f"Health check database query failed: {e}")
        
    llm_configured = bool(LLM_API_KEY)
    
    if db_connected and llm_configured:
        server_status = "healthy"
    elif db_connected:
        server_status = "degraded"
    else:
        server_status = "unhealthy"
        
    return {
        "status": server_status,
        "database_connected": db_connected,
        "llm_configured": llm_configured,
        "project": "AI-Based Education Recommendation System"
    }

# -----------------------------------
# INCLUDE ROUTES
# -----------------------------------

app.include_router(
    auth_router,
    prefix="/api/auth",
    tags=["Authentication"]
)

app.include_router(
    user_router,
    prefix="/api/users",
    tags=["Users"]
)

app.include_router(
    task_router,
    prefix="/api/tasks",
    tags=["Tasks"]
)

app.include_router(
    analytics_router,
    prefix="/api/analytics",
    tags=["Analytics"]
)

app.include_router(
    resource_router,
    prefix="/api/resources",
    tags=["Resources"]
)

app.include_router(
    schedule_router,
    prefix="/api/schedule",
    tags=["Schedule"]
)

app.include_router(
    subject_router,
    prefix="/api/subjects",
    tags=["Subjects"]
)

app.include_router(
    milestone_routes.router,
    prefix="/api/milestones",
    tags=["Milestones"]
)

app.include_router(
    profile_router,
    prefix="/api/profile",
    tags=["Profile"]
)

app.include_router(
    notification_router,
    prefix="/api/notifications",
    tags=["Notifications"]
)

app.include_router(
    study_session_router,
    prefix="/api/study-sessions",
    tags=["Study Sessions"]
)