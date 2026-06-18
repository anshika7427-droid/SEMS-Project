# Smart Education Management System (SEMS)

An AI-powered student productivity platform designed to optimize study schedules, track milestones, manage course tasks, and recommend tailored academic resources.

---

## Architecture

SEMS is structured as a decoupled web application containing a robust FastAPI backend API and a responsive, interactive frontend layer.

### Backend (FastAPI)
- **Framework**: FastAPI for async endpoint handling, automatic documentation, and path operations.
- **ORM & Database**: SQLAlchemy mapping Python objects to a local SQLite database file.
- **Validation**: Pydantic schemas validating schemas on creation, update, and response serialize stages.
- **Security**: 
  - Session-based authentication using FastAPI's custom cookies wrapper.
  - Insecure defaults protection (application fails startup if `SECRET_KEY` is not securely configured in environment).
  - Parameterized SQLite queries preventing SQL Injection.
  - Sanitization on filenames preventing Path Traversal vulnerabilities.

### Frontend
- **Interface**: Single-page templates built with modern Tailwind CSS (via CDN) and Google Fonts.
- **Reactivity**: Vanilla JavaScript handlers calling JSON backend endpoints, dynamically updating dashboard progress bars, event schedules, and milestone lists.

---

## Folder Structure

```
SEMS-Project/
├── app/                      # Backend Application source code
│   ├── routes/               # API Router modules defining endpoints
│   │   ├── analytics_routes.py
│   │   ├── auth_routes.py
│   │   ├── milestone_routes.py
│   │   ├── profile_routes.py
│   │   ├── resource_routes.py
│   │   ├── schedule_routes.py
│   │   ├── subject_routes.py
│   │   ├── task_routes.py
│   │   └── user_routes.py
│   ├── services/             # Core business logic layer
│   │   ├── ai_service.py
│   │   ├── auth_service.py
│   │   ├── llm_service.py
│   │   ├── milestone_service.py
│   │   ├── schedule_service.py
│   │   ├── subject_service.py
│   │   └── task_service.py
│   ├── utils/                # Utility helper modules
│   │   ├── helpers.py        # Log formatting & rate calculation helper
│   │   └── validators.py     # String & email format validation helper
│   ├── ai_engine.py          # Workload analysis & preset resource logic
│   ├── analytics.py          # Daily log-session tracking & streak logic
│   ├── auth.py               # Password hashing & current user resolver
│   ├── config.py             # Environment configuration & validation
│   ├── database.py           # SQLite db engine & connection pool setup
│   ├── main.py               # Main application definition & static mounts
│   ├── models.py             # SQLAlchemy models defining database tables
│   ├── scheduler.py          # Rule-based fallback study scheduler algorithm
│   └── schemas.py            # Pydantic validation schemas
├── database/                 # Directory holding runtime SQLite files
├── frontend/                 # Static frontend templates
│   ├── assets/               # Local images, upload resource storage
│   └── pages/                # Served HTML views (dashboard, profiles, etc.)
├── tests/                    # Integration and unit tests
│   ├── test_academic_core.py # Core models and validations tests
│   ├── test_ai.py            # Scheduler algorithms and analytics tests
│   ├── test_ai_schedule.py   # LLM mock schedule & calibration tests
│   ├── test_auth.py          # Authentication routes tests
│   └── test_routes.py        # CRUD route integration flows tests
├── requirements.txt          # Pinned project dependencies list
├── run.py                    # Subprocess launcher script
└── .env                      # Local configuration settings (ignored by git)
```

---

## Environment Variables

Configure these settings inside a `.env` file in the root directory. Use `.env.example` as a template.

| Variable Name | Description | Default / Example Value |
|---|---|---|
| `SECRET_KEY` | Hex/random string encrypting session cookies. **Must be set** (Application fails startup if empty or placeholder). | `your-secure-random-secret-key` |
| `LLM_API_KEY` | API Key for LLM services (e.g. Groq, OpenAI). | `gsk_...` |
| `LLM_MODEL` | Target language model for AI schedule generation. | `llama-3.3-70b` |
| `LLM_API_URL` | Base API URL serving the target model. | `https://api.groq.com/openai/v1` |

---

## Installation

### Prerequisites
- Python 3.10 or higher.
- Pip (Python Package Installer).

### Steps
1. **Clone the Repository**:
   ```bash
   git clone <repository_url>
   cd SEMS-Project
   ```

2. **Initialize Virtual Environment**:
   ```bash
   python -m venv venv
   # On Windows (PowerShell):
   .\venv\Scripts\Activate.ps1
   # On macOS/Linux:
   source venv/bin/activate
   ```

3. **Install Pinned Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Setup Environment Configuration**:
   Create a `.env` file in the project root:
   ```bash
   copy .env.example .env
   # Update the values inside .env with your LLM keys and a secure SECRET_KEY
   ```

---

## Running the Server

To start the FastAPI backend:

- **Using Launcher (Windows/Any)**:
  Runs uvicorn and opens the web application automatically in your default browser.
  ```bash
  python run.py
  ```

- **Using Uvicorn CLI Directly**:
  ```bash
  uvicorn app.main:app --reload --port 8000
  ```
  Once running, visit [http://127.0.0.1:8000](http://127.0.0.1:8000) in your browser.

---

## Running Tests

To verify backend routing, validations, authentication flows, and study planners:

```bash
# Activate virtualenv first, then run:
python -m pytest
```

---

## API Summary

All endpoints listed below are prefixed with `/api` unless serving static frontend HTML views.

### Authentication (`/api/auth`)
- `POST /register` & `POST /signup`: Register a new user profile.
- `POST /login`: Generate a cookie-backed session.
- `POST /logout`: Destroy the active user session.
- `GET /status` & `GET /me`: Return active user identity details.

### Subjects (`/api/subjects`)
- `POST /create`: Register a new subject.
- `GET /all` & `GET /`: Retrieve all subjects for the user.
- `GET /{subject_id}`: Get details of a single subject.
- `PUT /{subject_id}`: Edit subject details.
- `DELETE /{subject_id}`: Delete a subject.

### Tasks (`/api/tasks`)
- `POST /create`: Register a task under a subject.
- `GET /all` & `GET /`: Retrieve user tasks.
- `GET /{task_id}`: Get details of a single task.
- `PUT /{task_id}`: Update task properties.
- `DELETE /{task_id}`: Remove a task.
- `DELETE /delete-all`: Clear all tasks.
- `PUT /toggle/{task_id}`: Complete or restore task status.

### Milestones (`/api/milestones`)
- `POST /create`: Add an upcoming deadline/exam milestone.
- `GET /all` & `GET /`: Retrieve all active milestones.
- `GET /{milestone_id}`: Get a milestone by ID.
- `PUT /{milestone_id}`: Update milestone details (e.g. completion percentage).
- `DELETE /{milestone_id}`: Delete a milestone.

### Schedule Planner (`/api/schedule`)
- `POST /generate-ai`: Generate study events using the configured LLM API.
- `POST /generate`: Build fallback schedules using local rule-based heuristics.
- `GET /all`: Retrieve active scheduled events.
- `GET /analysis`: Retrieve deep schedule breakdown reports.
- `GET /calibration` & `POST /calibration`: Read or write target study hours, optimal focus periods, and method parameters.
- `DELETE /reset`: Wipe the calendar clear.

### Profile Manager (`/api/profile`)
- `GET /me`: Retrieve statistics and personal info.
- `PUT /me`: Modify username or email.
- `PUT /change-password`: Update account password.
- `POST /avatar`: Upload user avatar image (png, jpg, webp).

### Performance Analytics (`/api/analytics`)
- `GET /summary`: Combine progress rates and AI recommendations.
- `POST /log-session`: Log a study session (duration in minutes and type).

---

## Production Deployment

### 1. Docker & Docker Compose (Recommended)
You can deploy the entire application using Docker. The multi-stage build packages the backend application and copies only the required runtime files.

1. Configure production environment variables in a `.env` file (ensure `SECRET_KEY` is secure and `CORS_ORIGINS` points to production domains).
2. Start the services using docker-compose:
   ```bash
   docker-compose up -d --build
   ```
3. Docker Compose configures named volumes (`sems_data` and `sems_storage`) to persist the SQLite database and uploaded profile avatars across container restarts.

### 2. Manual Production Execution
To host manually on a production server:
1. Set the production environment variables:
   ```bash
   export SECRET_KEY="a-very-long-secure-random-key"
   export LLM_API_KEY="your-production-llm-key"
   export CORS_ORIGINS="https://yourdomain.com"
   export HOST="0.0.0.0"
   export PORT="8000"
   ```
2. Run database migrations:
   ```bash
   alembic upgrade head
   ```
3. Run the FastAPI application using Gunicorn with Uvicorn workers:
   ```bash
   gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8000
   ```

