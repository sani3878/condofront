# CondoFront

Parcel management SaaS for condominium juristic offices.

## Stack
- Python 3.11 + Flask
- PostgreSQL
- Bootstrap 5
- Flask-Login

## Project Structure

```
condofront/
├── run.py                  # Entry point
├── config.py               # Dev/prod config
├── requirements.txt
├── .env.example            # Copy to .env and fill in
│
└── app/
    ├── __init__.py         # App factory (create_app)
    ├── extensions.py       # Flask-Login setup
    ├── helpers.py          # DB helpers: query_one, query_all, execute
    ├── decorators.py       # @roles_required, @admin_only
    ├── models.py           # User model for Flask-Login
    │
    ├── auth/               # Login, register, logout
    ├── parcel/             # Receive, list, pickup, print label
    ├── property/           # Setup, rooms, staff users
    ├── report/             # Dashboard, reports
    ├── admin/              # CondoFront super admin
    │
    ├── static/
    │   ├── css/
    │   ├── js/
    │   └── img/
    │
    └── templates/
        ├── shared/         # base.html, navbar.html
        ├── auth/
        ├── parcel/
        ├── property/
        ├── report/
        └── admin/
```

## Setup

```bash
cp .env.example .env
# Edit .env with your database URL and secret key

pip install -r requirements.txt
python run.py
```

## Role IDs (from tblrole)
- 1 = Admin      (CondoFront super admin)
- 2 = Manager    (Property manager — full access)
- 3 = Reception  (Day-to-day parcel operations)
- 4 = Security   (Receive parcels only)
