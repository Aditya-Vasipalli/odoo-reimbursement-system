# Reimbursement Management System

Hackathon scaffold for Odoo x VIT Pune.

## Run Backend

```bash
cd backend
python -m venv venv
# Windows
venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

## Run Frontend Shell

```bash
cd frontend
python -m http.server 3000
```

## Environment

Create a `.env` file in `reimbursement-app/`:

```env
DATABASE_URL=postgresql://postgres:password@localhost:5432/reimbursement
JWT_SECRET=changeme_hackathon_secret
```
