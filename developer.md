# Developer Guide

## Overview
The **busqueda_hostipal** project is a Flask‑based web application that provides:
- A **public search** interface for hospital data.
- An **admin panel** for managing users and persons (patients).
- **CSV export** of the public data.
- **Google‑Sheets synchronization** (planned).
- **Docker** support for easy deployment.

---

## Project Layout
```
busqueda_hostipal/
├─ app/                     # Application package
│   ├─ __init__.py          # Flask app factory, blueprint registration
│   ├─ public.py            # Public blueprint (search page)
│   ├─ admin.py             # Admin blueprint (dashboard, CRUD, CSV)
│   ├─ auth.py              # Login/Logout routes (uses Flask‑Login)
│   ├─ models.py           # SQLAlchemy models (User, Person, etc.)
│   ├─ forms.py            # WTForms for login, user, person
│   ├─ scheduler.py        # APScheduler background jobs
│   └─ sync.py             # Google‑Sheets sync logic (placeholder)
├─ migrations/             # Alembic migration scripts (generated)
├─ static/
│   ├─ css/style.css       # Premium UI styling (variables, glassmorphism)
│   └─ js/charts.js        # Helper for Chart.js graphs
├─ templates/
│   ├─ admin/
│   │   ├─ dashboard.html # Admin dashboard with export button
│   │   ├─ users.html     # Users list (DataTables)
│   │   ├─ user_form.html # Create/Edit user form
│   │   ├─ persons.html   # Persons list (DataTables)
│   │   └─ person_form.html # Create/Edit person form
│   └─ public/
│       └─ search.html   # Public search page (DataTables)
├─ Dockerfile               # Multi‑stage build, installs deps, runs gunicorn
├─ docker-compose.yml       # Service definition (web) exposing 5000
├─ README.md                # User‑facing instructions (already exists)
├─ requirements.txt         # Python dependencies
└─ run.py                   # Entry point `create_app()` and `app.run()`
```
---

## Core Components
### `app/__init__.py`
- Creates the Flask app instance.
- Loads configuration from `app.config.Config`.
- Initializes extensions: **SQLAlchemy**, **LoginManager**, **Migrate**, **APScheduler**.
- Registers three blueprints:
  - `public_bp` – routes under `/public`.
  - `auth_bp` – routes for login/logout.
  - `admin_bp` – routes under `/admin` (CRUD, CSV).
- Calls `init_scheduler(app)` to start background jobs.

### Blueprints
- **Public Blueprint (`app/public.py`)**
  - `GET /public/search` → renders `templates/public/search.html`.
  - Queries the `Person` model and returns JSON for DataTables.
- **Admin Blueprint (`app/admin.py`)**
  - Dashboard (`/admin/`) shows simple stats and an *Export CSV* button.
  - CRUD routes for **User** and **Person** using WTForms (`UserForm`, `PersonForm`).
  - CSV export (`/admin/export_csv`) streams a CSV built with **pandas**.
- **Auth Blueprint (`app/auth.py`)**
  - `GET /login` and `POST /login` – uses `LoginForm`.
  - `GET /logout` – logs out the user.
  - `login_manager.user_loader` loads a `User` by ID.

### Models (`app/models.py`)
```python
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    role = db.Column(db.String(50), nullable=False)
    # password hash, etc.

class Person(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    hospital = db.Column(db.String(100))
    phone = db.Column(db.String(20))
    family = db.Column(db.String(100))
    age = db.Column(db.Integer)
    has_relative = db.Column(db.Boolean, default=False)
    # timestamps, foreign keys, etc.
```
All models are imported in `app/__init__.py` so Alembic sees them.

### Forms (`app/forms.py`)
- **LoginForm** – email, password.
- **UserForm** – email, role.
- **PersonForm** – fields matching `Person` model.
All inherit from `FlaskForm` and use validators (`DataRequired`, `Email`, `Length`).

### Scheduler (`app/scheduler.py`)
```python
from apscheduler.schedulers.background import BackgroundScheduler

def dummy_job():
    pass

def init_scheduler(app):
    scheduler = BackgroundScheduler()
    scheduler.add_job(func=dummy_job, trigger='interval', seconds=60, id='dummy')
    scheduler.start()
```
The placeholder job shows where a real sync job (e.g., pulling Google‑Sheets) would be scheduled.

### Sync (`app/sync.py`)
- Intended to contain the logic that pulls data from a Google Sheet using **gspread** and updates the DB.
- Not yet filled; the project scaffolding includes the file and required dependencies.

---

## Static Assets
- **CSS (`static/css/style.css`)** – uses CSS variables for primary/secondary colors, implements a subtle glass‑morphism card style, and provides responsive layout utilities.
- **JS (`static/js/charts.js`)** – tiny wrapper to initialise Chart.js charts on the admin dashboard (e.g., counts per hospital).

---

## Database Migration Workflow
1. Ensure the virtual environment is activated.
2. Install requirements: `pip install -r requirements.txt`.
3. Initialise Alembic (already done): `flask db init` creates `migrations/`.
4. Create a migration after model changes: `flask db migrate -m "description"`.
5. Apply migration: `flask db upgrade`.
The generated migration files live under `migrations/versions/`.

---

## Running the Application
### Locally (development)
```bash
# activate venv
source venv/Scripts/activate   # PowerShell
pip install -r requirements.txt
flask run --host=0.0.0.0 --port=5000
```
- Visit `http://localhost:5000/public/search` for the public view.
- Visit `http://localhost:5000/admin/` (login required) for admin.

### With Docker
```bash
docker compose up --build
```
The container runs `gunicorn -w 4 -b 0.0.0.0:5000 run:app`.
Port 5000 is exposed on the host.

---

## Extending the Project
- **Add new background jobs**: create a function in `app/scheduler.py` and register it with `scheduler.add_job`.
- **Google‑Sheets sync**: implement `sync_google_sheet()` in `app/sync.py` using the `gspread` credentials file placed in the project root.
- **API layer**: add a `api` blueprint under `app/api.py` and expose JSON endpoints.
- **Tests**: add `tests/` directory with `pytest` suites, run via `pytest`.

---

## Summary
The code follows a classic **Flask application factory** pattern, cleanly separating concerns via blueprints, SQLAlchemy models, WTForms, and background scheduling. All static assets and templates are under `static/` and `templates/`. Docker support and a comprehensive `README.md` make deployment straightforward.

For any further development, edit the appropriate blueprint or model, generate a migration, and redeploy.
