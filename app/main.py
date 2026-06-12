from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, RedirectResponse
from starlette.middleware.sessions import SessionMiddleware
from pathlib import Path

# -----------------------------------
# IMPORT DATABASE
# -----------------------------------

from app.database import engine
from app.models import Base
from app.config import SECRET_KEY

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

# -----------------------------------
# CREATE DATABASE TABLES
# -----------------------------------

Base.metadata.create_all(bind=engine)

# -----------------------------------
# FASTAPI APP
# -----------------------------------

app = FastAPI(
    title="AI-Based Education Recommendation System",
    description="Modern AI Student Productivity Platform",
    version="1.0.0"
)

# -----------------------------------
# SESSION MIDDLEWARE
# -----------------------------------

app.add_middleware(
    SessionMiddleware,
    secret_key=SECRET_KEY,
    session_cookie="session",
    max_age=14 * 24 * 3600  # 14 days
)

# -----------------------------------
# CORS CONFIG
# -----------------------------------

# Using specific allowed origins rather than "*" to support credentials (session cookies)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:8000",
        "http://localhost:8000"
    ],
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
    return {
        "status": "running",
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

app.include_router(subject_router)

app.include_router(milestone_routes.router)