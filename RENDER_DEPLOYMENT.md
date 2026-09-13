# CampusX Render Deployment Guide

## Table of Contents

- [A. GitHub Requirements](#a-github-requirements)
- [B. Render Account Setup](#b-render-account-setup)
- [C. Backend Web Service Creation](#c-backend-web-service-creation)
- [D. Frontend Web Service Creation](#d-frontend-web-service-creation)
- [E. Environment Variables](#e-environment-variables)
- [F. CORS Configuration](#f-cors-configuration)
- [G. Database Configuration](#g-database-configuration)
- [H. Groq Configuration](#h-groq-configuration)
- [I. Health Check Configuration](#i-health-check-configuration)
- [J. Build/Start Configuration](#j-buildstart-configuration)
- [K. Deployment Steps](#k-deployment-steps)
- [L. Common Deployment Errors](#l-common-deployment-errors)
- [M. How to Redeploy](#m-how-to-redeploy)
- [N. How to Inspect Render Logs](#n-how-to-inspect-render-logs)
- [O. Database Migration Notes](#o-database-migration-notes)

---

## A. GitHub Requirements

1. **Repository must be on GitHub** (public or private)
2. **Main branch** should contain the latest code
3. **Dockerfiles** must be present at:
   - `Dockerfile` (root) — Frontend Next.js
   - `backend/Dockerfile` — Backend FastAPI
4. **`.env.local` must NOT be committed** — it is in `.gitignore`
5. **`render.yaml`** Blueprint is included in the repository root

---

## B. Render Account Setup

1. Sign up at [render.com](https://render.com)
2. Connect your GitHub account
3. Ensure your repository is accessible to Render

---

## C. Backend Web Service Creation

### Option 1: Manual Creation

1. Click **"New"** > **"Web Service"**
2. Connect your GitHub repository
3. Configure:
   - **Name:** `campusx-backend`
   - **Runtime:** `Docker`
   - **Dockerfile Path:** `backend/Dockerfile`
   - **Docker Context:** `.` (repo root)
   - **Port:** `8000` (will be overridden by PORT env var)
   - **Health Check Path:** `/api/v1/health`
   - **Plan:** Starter (or higher)

### Option 2: Blueprint

1. Click **"New"** > **"Blueprint"**
2. Connect your repository
3. Render detects `render.yaml` and creates both services
4. **Before deploying**, configure environment variables (see Section E)

---

## D. Frontend Web Service Creation

### Option 1: Manual Creation

1. Click **"New"** > **"Web Service"**
2. Connect your GitHub repository
3. Configure:
   - **Name:** `campusx-frontend`
   - **Runtime:** `Docker`
   - **Dockerfile Path:** `Dockerfile` (root)
   - **Docker Context:** `.` (repo root)
   - **Port:** `3000` (will be overridden by PORT env var)
   - **Plan:** Starter (or higher)

### Option 2: Blueprint

Created automatically with `render.yaml`. See Section B.

---

## E. Environment Variables

### Backend Environment Variables

Set these in the Render Dashboard for the **backend** service:

| Variable | Required | Description | Example |
|---|---|---|---|
| `DB_HOST` | Yes | Supabase database host | `aws-1-ap-south-1.pooler.supabase.com` |
| `DB_PORT` | Yes | Supabase database port | `6543` |
| `DB_NAME` | Yes | Database name | `postgres` |
| `DB_USER` | Yes | Database user | `postgres.your-project-ref` |
| `DB_PASSWORD` | Yes | Database password | *(secret)* |
| `JWT_SECRET` | Yes | JWT signing secret (>= 32 bytes) | *(secret)* |
| `GROQ_API_KEY` | Yes | Groq API key | *(secret)* |
| `CORS_ORIGINS` | Yes | Deployed frontend URL | `https://campusx-frontend.onrender.com` |
| `ENVIRONMENT` | No | Environment mode | `production` |
| `GENAI_PRIMARY_PROVIDER` | No | Primary LLM provider | `groq` |
| `GENAI_FALLBACK_PROVIDER` | No | Fallback provider (empty = none) | `""` |
| `GROQ_MODEL` | No | Groq model name | `openai/gpt-oss-120b` |
| `GROQ_BASE_URL` | No | Groq API endpoint | `https://api.groq.com/openai/v1` |
| `CURRENT_ACADEMIC_YEAR` | No | Academic year | `2026-27` |

### Frontend Environment Variables

Set these in the Render Dashboard for the **frontend** service:

| Variable | Required | Description | Example |
|---|---|---|---|
| `FASTAPI_URL` | Yes | Deployed backend URL | `https://campusx-backend.onrender.com` |
| `JWT_SECRET` | Yes | Same secret as backend (frontend signs JWTs on login) | *(secret)* |
| `NODE_ENV` | No | Node environment | `production` |
| `ENVIRONMENT` | No | Environment mode | `production` |
| `CURRENT_ACADEMIC_YEAR` | No | Academic year | `2026-27` |

**Why the frontend needs `JWT_SECRET`:** The Next.js frontend implements a BFF (Backend-for-Frontend) auth pattern. On login, `app/login/actions.ts` calls `signSession()` from `lib/auth-jwt.ts` to create a signed HS256 JWT stored in an HttpOnly cookie. On every subsequent request, the frontend verifies the JWT using the same secret. The backend also receives this JWT in the `Authorization` header and verifies it with the same secret. Both services **must** share the identical `JWT_SECRET`.

---

## F. CORS Configuration

The backend uses `CORS_ORIGINS` to control which frontend domains can make requests.

### Setting CORS for Render

In the **backend** service environment variables:

```
CORS_ORIGINS=https://campusx-frontend.onrender.com
```

For multiple origins (comma-separated or JSON array):

```
CORS_ORIGINS=https://campusx-frontend.onrender.com,http://localhost:3000
```

**Important:** Do NOT use `*` when credentials/cookies are involved.

---

## G. Database Configuration

### Using Existing Supabase PostgreSQL

This deployment uses the **existing Supabase-hosted PostgreSQL database**. No Render PostgreSQL service is created.

Set these in the backend:

```
DB_HOST=aws-1-ap-south-1.pooler.supabase.com
DB_PORT=6543
DB_NAME=postgres
DB_USER=postgres.your-project-ref
DB_PASSWORD=your-supabase-password
```

### SSL Configuration

The backend auto-detects Supabase (checks if `DB_HOST` contains "supabase" or `DB_PORT == 6543`) and enables SSL automatically.

---

## H. Groq Configuration

The application uses Groq as the primary LLM provider. Set these in the backend:

```
GENAI_PRIMARY_PROVIDER=groq
GENAI_FALLBACK_PROVIDER=
GROQ_API_KEY=your-groq-api-key
GROQ_MODEL=openai/gpt-oss-120b
GROQ_BASE_URL=https://api.groq.com/openai/v1
```

**Notes:**
- `GROQ_API_KEY` is required for chat/copilot features
- `GENAI_FALLBACK_PROVIDER` is set to empty string — Ollama is NOT available on Render
- If Groq is unavailable, the chat feature will return an appropriate error
- Ollama is only a local development fallback; do not configure it for Render

---

## I. Health Check Configuration

### Backend Health Check

- **Endpoint:** `GET /api/v1/health`
- **Expected Response:** `{"status": "healthy", "database": "connected"}`
- **Render Config:** Health Check Path = `/api/v1/health`
- **Response Timeout:** 30 seconds

### Docker Health Check

The backend Dockerfile includes a built-in health check that polls `/api/v1/health` every 30 seconds.

---

## J. Build/Start Configuration

### Backend

- **Base Image:** `python:3.12-slim`
- **Build:** `pip install --no-cache-dir -r requirements.txt`
- **Start:** `uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}`
- **PORT:** Configurable via `PORT` env var (default: 8000)
- **Includes:** `backend/app` + `ml/` (ML model artifacts)

### Frontend

- **Base Image:** `node:20-alpine`
- **Build:** `npm ci && npm run build` (standalone output)
- **Start:** `node server.js`
- **PORT:** Configurable via `PORT` env var (default: 3000)

---

## K. Deployment Steps

### Step 1: Pre-Deployment Checklist

- [ ] `.env.local` is NOT committed to Git
- [ ] `render.yaml` is in the repository root
- [ ] Existing Supabase database is accessible from Render (check IP whitelist)
- [ ] Groq API key is valid
- [ ] Database schema is already applied (see Section O)

### Step 2: Deploy Backend

1. Create or select the backend Web Service
2. Set all required environment variables (see Section E)
3. Deploy and wait for the first build to complete
4. Verify: `GET https://campusx-backend.onrender.com/api/v1/health`
5. Expected: `{"status":"healthy","database":"connected"}`

### Step 3: Deploy Frontend

1. Create or select the frontend Web Service
2. Set all required environment variables (see Section E)
3. Set `FASTAPI_URL` to the backend's Render URL (e.g., `https://campusx-backend.onrender.com`)
4. Set `JWT_SECRET` to the **same value** used by the backend
5. Deploy and wait for the first build to complete
6. Visit: `https://campusx-frontend.onrender.com`

### Step 4: Post-Deployment Verification

1. Backend health check returns `{"status":"healthy","database":"connected"}`
2. Frontend loads the login page
3. Login works with existing credentials
4. Chat/copilot feature works (requires Groq API key)

---

## L. Common Deployment Errors

### 1. `DB_PASSWORD is not set`

**Cause:** Backend starts without database credentials.
**Fix:** Set `DB_PASSWORD` in the backend environment variables.

### 2. CORS Error / Blocked by CORS Policy

**Cause:** Frontend URL not in `CORS_ORIGINS`.
**Fix:** Set `CORS_ORIGINS=https://your-frontend.onrender.com` in backend env vars.

### 3. `FASTAPI_URL` Connection Refused

**Cause:** Frontend can't reach the backend.
**Fix:** Set `FASTAPI_URL` to the backend's Render URL (e.g., `https://campusx-backend.onrender.com`).

### 4. Build Fails - Node Version

**Cause:** Node.js version incompatibility.
**Fix:** Ensure `node:20-alpine` is used in the frontend Dockerfile (already configured).

### 5. Build Fails - Python Dependencies

**Cause:** `scikit-learn` or other ML dependencies fail to install.
**Fix:** Ensure `python:3.12-slim` base image is used (already configured).

### 6. Ollama Connection Errors

**Cause:** Application tries to connect to Ollama at localhost:11434.
**Fix:** Set `GENAI_FALLBACK_PROVIDER=""` (empty) so no fallback is configured.

### 7. Health Check Fails

**Cause:** Backend takes too long to start (ML model loading).
**Fix:** The Docker health check has a 15-second start period. ML models are loaded lazily on first request, not at startup.

### 8. `JWT_SECRET` Mismatch

**Cause:** Frontend and backend use different JWT secrets.
**Fix:** Set `JWT_SECRET` to the **same value** on both services.

### 9. Render Free Tier Spins Down

**Cause:** Free tier services spin down after inactivity.
**Fix:** Upgrade to a paid plan.

---

## M. How to Redeploy

### Automatic Redeploy

Render automatically redeploys when you push to the connected branch.

### Manual Redeploy

1. Go to the service in Render Dashboard
2. Click **"Manual Deploy"** > **"Deploy latest commit"**

### Clear Build Cache

If builds fail due to cache issues:

1. Go to the service in Render Dashboard
2. Click **"Manual Deploy"** > **"Clear build cache & deploy"**

---

## N. How to Inspect Render Logs

### Backend Logs

1. Go to the backend service in Render Dashboard
2. Click **"Logs"** tab
3. Filter by:
   - `stdout` — Application logs
   - `stderr` — Error logs
   - `build` — Build-time logs

### Frontend Logs

1. Go to the frontend service in Render Dashboard
2. Click **"Logs"** tab
3. Check for:
   - Build errors (npm install, next build)
   - Runtime errors (server.js startup)

### Shell Access

Render does not provide shell access to running services. Use logs for debugging.

---

## O. Database Migration Notes

### Critical Finding

The base table DDL (CREATE TABLE statements for 13 core tables) is **NOT in the repository**. These tables were created directly in the Supabase database console and never scripted into version control.

The `migrations/` directory contains:
- **Files 01–13:** Seed data (INSERT statements) — require base tables to exist
- **Files 14–23:** DDL extensions (ALTER TABLE, CREATE TABLE) — mostly idempotent

### What This Means for Deployment

**The existing Supabase database already has all tables and data.** No migration execution is needed for a standard deployment. The application connects to the existing database and works as-is.

### If You Need to Set Up a Fresh Database

This requires two steps that are **outside the scope of Render deployment**:

1. **Export the base schema** from the existing Supabase database:
   ```bash
   pg_dump --schema-only --no-owner --no-privileges \
     -h aws-1-ap-south-1.pooler.supabase.com \
     -p 6543 \
     -U postgres.your-project-ref \
     -d postgres \
     > base_schema.sql
   ```

2. **Apply the schema** to the new database, then apply seed data files 01–13 and DDL extensions 14–23 in order.

### Migration Files Are NOT Executed Automatically

- The backend does NOT run migrations on startup
- The Dockerfiles do NOT execute SQL files
- The `render.yaml` does NOT include migration steps
- The development `/seed` endpoint is NOT available in production (`NODE_ENV !== "development"`)

### Why Seed Files Cannot Be Re-Run

Files 01–13 use plain `INSERT INTO` without `ON CONFLICT` clauses. Re-running them on an existing database **duplicates all seed data**. Only the DDL extensions (files 14–23) are safe to re-run due to `IF NOT EXISTS` guards.

---

## Environment Variables Summary

### Render Production (Environment Variables)

```env
# Backend
DB_HOST=aws-1-ap-south-1.pooler.supabase.com
DB_PORT=6543
DB_NAME=postgres
DB_USER=postgres.your-project-ref
DB_PASSWORD=your-supabase-password
JWT_SECRET=your-jwt-secret
CORS_ORIGINS=https://campusx-frontend.onrender.com
GENAI_PRIMARY_PROVIDER=groq
GENAI_FALLBACK_PROVIDER=
GROQ_API_KEY=your-groq-key
GROQ_MODEL=openai/gpt-oss-120b
GROQ_BASE_URL=https://api.groq.com/openai/v1
ENVIRONMENT=production

# Frontend
FASTAPI_URL=https://campusx-backend.onrender.com
JWT_SECRET=your-jwt-secret
NODE_ENV=production
ENVIRONMENT=production
```
