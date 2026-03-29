# Reimbursement Management System

Hackathon scaffold for Odoo x VIT Pune.

## Prerequisites

- Python 3.11+
- PostgreSQL 14+

## PostgreSQL Setup (Required)

1. Start PostgreSQL.
	- Windows service UI: run `services.msc`, find PostgreSQL, click Start.
	- Or (if installed with pg_ctl):

```powershell
& "C:\Program Files\PostgreSQL\18\bin\pg_ctl.exe" -D "C:\Program Files\PostgreSQL\18\data" start
```

2. Set password for `postgres` user (if needed):

```powershell
psql -U postgres -d postgres -c "ALTER USER postgres WITH PASSWORD '1234';"
```

3. Create app database:

```powershell
psql -U postgres -d postgres -c "CREATE DATABASE reimbursement;"
```

## Environment

Create `.env` in the repository root:

```env
DATABASE_URL=postgresql://postgres:1234@localhost:5432/reimbursement
JWT_SECRET=changeme_hackathon_secret
```

## Backend Setup

Run from repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -r backend/requirements.txt
python -m uvicorn backend.main:app --reload --port 8000
```

Notes:
- Start from repository root so `backend.*` imports resolve.
- Tables are auto-created on startup.

Backend URLs:
- Health: `http://127.0.0.1:8000/`
- Swagger: `http://127.0.0.1:8000/docs`

## Frontend Shell

```powershell
cd frontend
python -m http.server 3000
```

Frontend URL:
- `http://localhost:3000`
