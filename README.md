# Viridis

Viridis is a hospital sustainability platform with a React dashboard frontend
and a FastAPI backend for emissions, reporting, benchmarking, scoring, and
forecasting workflows.

## Project Structure

- `viridis-green-hub/` - Vite, React, TypeScript, Tailwind, shadcn/Radix UI frontend.
- `backend/` - FastAPI, SQLAlchemy, Alembic, pandas, and scikit-learn backend.

## Prerequisites

- Node.js 20 or newer
- npm 10 or newer
- Python 3.12
- PostgreSQL, or another SQL database supported by SQLAlchemy

## Backend Setup

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Edit `backend/.env` and set `DATABASE_URL` for your local database.

Run the API:

```powershell
uvicorn app.main:app --reload
```

The API defaults to `http://localhost:8000`.

## Frontend Setup

This project uses npm as the frontend package manager. Keep
`package-lock.json` committed and do not add another package-manager lockfile.

```powershell
cd viridis-green-hub
npm ci
npm run dev
```

The Vite app defaults to `http://localhost:5173`.

## Useful Commands

```powershell
# Frontend
cd viridis-green-hub
npm run lint
npm run build

# Backend
cd backend
uvicorn app.main:app --reload
```

## Environment Files

Real `.env` files are intentionally ignored by Git. Use checked-in
`.env.example` files as templates.
