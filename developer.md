# Developer Guide

## Architecture

Flask application factory pattern with blueprints. SQLite (file-based, single-process). Sync workers via Gunicorn.

```
Request → Gunicorn (sync workers) → Flask app → Blueprints → SQLAlchemy → SQLite
                                                              ↓
                                              Telegram bot (inline webhook)
```

## Project Structure

```
busqueda_hostipal/
├── app/
│   ├── __init__.py          # App factory: create_app(), extensions, blueprint registration
│   ├── config.py            # Flask config class (SQLite URI, secret key, etc.)
│   ├── models.py            # SQLAlchemy models: Person, User, Hospital, Area, Estado, Estatus, AuditLog, SyncLog
│   ├── forms.py             # WTForms: LoginForm, UserForm, PersonForm
│   ├── public.py            # Public blueprint: search page + JSON API
│   ├── admin.py             # Admin blueprint: dashboard, CRUD persons/users/catalogs, Excel upload, CSV export, sync
│   ├── auth.py              # Auth blueprint: login/logout, Flask-Login integration
│   ├── telegram_bot.py      # Telegram bot: webhook handler, inline keyboard menu, search by cedula/name
│   ├── sync.py              # Google Sheets sync: get_gspread_client(), sync_sheet_to_db()
│   └── scheduler.py         # APScheduler: hourly sync background job
├── templates/
│   ├── base.html            # Base layout (Bootstrap 5, sidebar, nav)
│   ├── admin/               # Admin panel templates (dashboard, persons, users, catalogs, upload)
│   ├── public/              # Public templates (search.html, error pages)
│   └── auth/                # Login template
├── static/
│   ├── css/style.css        # Custom CSS (glassmorphism, variables, responsive)
│   └── js/charts.js         # Chart.js initialization
├── Dockerfile               # Python 3.11-slim, entrypoint.sh
├── entrypoint.sh            # Creates DB, runs migrations, seeds data, starts Gunicorn
├── docker-compose.yml       # Local Docker compose
├── run.py                   # Entry point: create_app() + app.run()
├── requirements.txt         # Python dependencies
├── .railwayignore           # Files excluded from Railway deploy
└── botinfo.txt              # Bot token (sensitive — excluded from deploy)
```

## Models (`app/models.py`)

### Person (table: `persons`)
Main entity. Stores patient data with FK relationships.

| Column             | Type        | Notes                              |
|--------------------|-------------|-------------------------------------|
| `id`               | Integer PK  |                                     |
| `nombre`           | String(120) | NOT NULL                            |
| `apellido`         | String(120) |                                     |
| `cedula`           | String(30)  | National ID                         |
| `sexo`             | String(20)  | Normalized: Masculino / Femenino    |
| `edad`             | Integer     |                                     |
| `estado_id`        | FK → Estado |                                     |
| `hospital_id`      | FK → Hospital |                                   |
| `area_id`          | FK → Area   |                                     |
| `estado_salud`     | Text        | Descripción libre                   |
| `tiene_familiar`   | Boolean     | default=False                       |
| `nombre_familiar`  | String(200) |                                     |
| `telefono`         | String(80)  |                                     |
| `estatus`          | String(30)  | Hospitalizado / Trasladado / Alta / Fallecido / No localizado |
| `observaciones`    | Text        |                                     |
| `sheet_row`        | Integer     | Fila en Google Sheet (para tracking)|
| `fecha_registro`   | DateTime    | default=utcnow                      |
| `created_at`       | DateTime    | default=utcnow                      |

Relations: `estado` → Estado, `hospital` → Hospital, `area` → Area.

### User (table: `users`)
Authentication with Flask-Login.

| Column          | Type        | Notes                         |
|-----------------|-------------|-------------------------------|
| `id`            | Integer PK  |                               |
| `username`      | String(80)  | unique                        |
| `password_hash` | String(255) | Werkzeug generate_password_hash |
| `nombre`        | String(120) |                               |
| `apellido`      | String(120) |                               |
| `role`          | String(20)  | admin / helper / viewer       |
| `active`        | Boolean     | default=True                  |
| `created_at`    | DateTime    |                               |

### Supporting tables
- **Estado**: id, nombre (unique) — states/provinces
- **Hospital**: id, nombre (unique), estado_id → FK → Estado
- **Area**: id, nombre (unique)
- **Estatus**: id, nombre (unique) — seeded on startup
- **AuditLog**: user_id, username, action, target_type, target_id, details, created_at
- **SyncLog**: imported, duplicated, started_at, finished_at

## Blueprints

### Public (`/public`)
- `GET /public/search` — Search page with stats (total persons, hospitals, areas, last update)
- `GET /public/api/persons` — JSON endpoint with filters (nombre, estado_id, hospital_id, area_id)

### Auth (`/auth`)
- `GET/POST /auth/login` — Login form
- `GET /auth/logout` — Logout

### Admin (`/admin`)
All routes require `@login_required`. Role checks via `require_role()`.

| Route                        | Methods   | Roles     | Description                  |
|------------------------------|-----------|-----------|------------------------------|
| `/admin/`                    | GET       | all*      | Dashboard                    |
| `/admin/persons`             | GET       | all*      | Person list (DataTable)      |
| `/admin/persons/new`         | GET/POST  | admin, helper | Create person           |
| `/admin/persons/<id>/edit`   | GET/POST  | admin, helper | Edit person             |
| `/admin/persons/<id>/delete` | POST      | admin, helper | Delete person           |
| `/admin/api/persons/list`    | GET       | all*      | JSON persons + filters      |
| `/admin/users`               | GET/POST  | admin, helper | User management        |
| `/admin/upload`              | GET/POST  | admin, helper | Excel upload + preview  |
| `/admin/upload/confirm`      | POST      | admin, helper | Confirm uploaded data |
| `/admin/catalogs`            | GET/POST  | admin, helper | Estado/Hospital/Area CRUD |
| `/admin/export_csv`          | GET       | admin     | CSV export                  |
| `/admin/sync`                | POST      | admin     | Force Google Sheets sync    |

*viewer can only view dashboard and persons list (no edit/delete/upload/catalogs/users/sync)

### Telegram Bot (`/telegram`)
- `POST /telegram/webhook` — Receives updates from Telegram API via webhook
- No auth needed (public search)
- Inline keyboard menu with 3 search modes: cedula / nombre+apellido / nombre|apellido
- Pagination (10 results per page)
- Detail view with all patient fields
- State persisted per chat in `instance/search_cache.json` (shared across Gunicorn workers)

## RBAC System

```python
def require_role(*roles):
    if current_user.role not in roles:
        abort(403)
```

Applied at route level. All admin routes check roles. Sync is admin-only. Viewer gets read-only dashboard + person list (no edit/delete/upload/catalogs/users/sync).

## Excel Upload Flow

1. `POST /admin/upload` — parse file with pandas + openpyxl
2. Preview with "Acción" column (Crear / Actualizar) based on dedup logic
3. `POST /admin/upload/confirm` — batch insert/update in transaction

### Deduplication logic
- If `cedula` is present and not "N": match by cedula → existing → update
- If `cedula` is "N" or empty: match by nombre + apellido (case-insensitive) → existing → update
- No match → create new record
- Sexo normalization: "M" → "Masculino", "F" → "Femenino" (also in preview)

## Google Sheets Sync (`app/sync.py`)

### Credential loading order
1. `GOOGLE_SERVICE_ACCOUNT_JSON` (env var) or `GOOGLE_SERVICE_ACCOUNT_PRIVATE_KEY_JSON` (Railway)
   - Parse JSON → convert `\n` in private_key to real newlines → authorize with gspread
2. Fallback: individual variables `GOOGLE_SERVICE_ACCOUNT_EMAIL` + `GOOGLE_SERVICE_ACCOUNT_PRIVATE_KEY`
   - Strip surrounding quotes, convert `\n` → build service account info dict → authorize

### Sync process
- Read all rows from Google Sheet
- Match by sheet_row → update existing / insert new
- Log results in SyncLog
- Run hourly via APScheduler or manual trigger from admin dashboard

## Telegram Bot Design

### Webhook flow (no polling)
```
Telegram → POST /telegram/webhook → Flask handler → process update → respond via Telegram API
```

### State management
- Each chat's last query and search mode stored in `instance/search_cache.json`
- If a different Gunicorn worker handles the callback, it reloads the query from file and re-runs the DB search
- In-memory cache (`_search_cache` dict) for fast pagination within same worker

### Search modes
- **cedula**: `Person.cedula.ilike(f"%{q}%")`
- **fullname**: split query in 2, `Person.nombre.ilike(first) & Person.apellido.ilike(last)`
- **name**: `Person.nombre.ilike(q) | Person.apellido.ilike(q)`

## Railway Deployment

- **Dockerfile**: python:3.11-slim, installs deps, copies app, entrypoint.sh
- **entrypoint.sh**:
  1. Create `/app/instance` directory
  2. Run inline Python: create_app() → db.create_all() → seed_estatuses()
  3. Start Gunicorn: `gunicorn --bind 0.0.0.0:5000 --workers 2 run:app`
- **Database**: SQLite at `/app/instance/database.db` (persisted via Railway volume)
- **Webhook**: first Gunicorn worker to boot sets the Telegram webhook, creates flag file `.webhook_set` so other workers skip

### Required environment variables
| Variable                  | Required   | Notes                                     |
|---------------------------|------------|-------------------------------------------|
| `SECRET_KEY`              | Yes        | Flask secret                              |
| `GOOGLE_SHEET_ID`         | For sync   | Google Sheet ID                           |
| `GOOGLE_SERVICE_ACCOUNT_EMAIL` | For sync | Service account email                   |
| `GOOGLE_SERVICE_ACCOUNT_PRIVATE_KEY` | For sync | Private key (with `\n`)        |
| `TELEGRAM_BOT_TOKEN`      | For bot    | From @BotFather                           |
| `TELEGRAM_WEBHOOK_URL`    | For bot    | Full URL to /telegram/webhook endpoint    |

### Railway-specific notes
- Railway sets `PORT` env var — Flask binds to it
- Instance directory `/app/instance` is writable via a Railway bind mount
- 2 Gunicorn workers default — sync workers, no async needed
- APScheduler runs in each worker — only one fires the sync job (no duplicate guard currently)

## Key Technical Decisions

| Decision | Rationale |
|----------|-----------|
| SQLite over PostgreSQL | Simpler setup, file-based backups, single server. Adequate for moderate traffic |
| APScheduler over Celery | Single-process app, no need for message broker |
| Direct Telegram API (requests) over python-telegram-bot | Avoid asyncio/Gunicorn conflicts. Synchronous, reliable with multi-worker |
| Webhook over polling | Railway-friendly (no long-running threads). Receives updates via HTTP |
| File-based search cache | Shared between workers via Railway volume. Simple, no external deps |
| `\n` replacement in private key | Railway env vars escape `\n` — must convert back for valid RSA key |
| Role-based access (3 roles) | Hospital staff needs different permission levels |
| Dedup by nombre+apellido when cedula unknown | Essential for emergency registrations where ID may not be available |
