# CampusX CI/CD Deployment Guide (Windows Self-Hosted Runner)

This guide documents the automated continuous deployment (CI/CD) setup for **CampusX**.

Any authorized developer who pushes code to the `main` branch of the GitHub repository triggers an automatic build and deployment directly on **your Windows PC**.

---

## 1. Architecture

```
Developer A / Developer B
       ↓ (git push origin main)
GitHub Repository (HarshGosalia05/ByteBrain)
       ↓ (Triggers .github/workflows/deploy.yml)
GitHub Actions
       ↓ (Dispatches job to runs-on: [self-hosted, Windows])
Your Windows PC (Self-Hosted Runner)
       ↓ (Checks out code into isolated runner workspace)
Docker Compose Rebuild & Update
  - Copies host environment (.env.local) securely
  - Validates compose configuration (docker compose config)
  - Rebuilds images safely (docker compose build)
  - Updates running containers in-place (docker compose up -d)
       ↓
Health Checks
  - Backend: http://localhost:8000/api/v1/health (status: healthy, database: connected)
  - Frontend: http://localhost:3000/login (HTTP 200)
       ↓
CampusX Automatically Updated on Your PC
```

---

## 2. One-Time Prerequisites on Your Windows PC

Ensure the following prerequisites are installed and running on your Windows machine:

1. **Docker Desktop for Windows**:
   - Must be running with Linux containers enabled.
   - Verify in PowerShell:
     ```powershell
     docker --version
     docker compose version
     ```
2. **Git**:
   - Verify in PowerShell:
     ```powershell
     git --version
     ```
3. **Environment Configuration**:
   - Ensure your verified `.env.local` file exists at:
     ```
     D:\KenexAi\ByteBrain\.env.local
     ```
   - *Never commit this file or its secret values to GitHub.*

---

## 3. One-Time Self-Hosted Runner Installation & Registration

The deployment workflow requires a GitHub Actions self-hosted runner installed on your Windows machine. Follow these official steps:

### Step 1: Open GitHub Runner Settings
1. Navigate to your repository on GitHub:
   ```
   https://github.com/HarshGosalia05/ByteBrain
   ```
2. Go to **Settings** > **Actions** > **Runners** (left sidebar).
3. Click the green **New self-hosted runner** button.
4. Select **Runner image**: **Windows**.
5. Select **Architecture**: **x64**.

### Step 2: Download the Runner
Open PowerShell as Administrator and create a dedicated runner directory:
```powershell
New-Item -ItemType Directory -Path "C:\actions-runner" -Force
Set-Location "C:\actions-runner"
```

Download the latest Windows x64 runner package shown on the GitHub page:
```powershell
Invoke-WebRequest -Uri https://github.com/actions/runner/releases/download/v2.322.0/actions-runner-win-x64-2.322.0.zip -OutFile actions-runner.zip
Expand-Archive -Path actions-runner.zip -DestinationPath .
Remove-Item actions-runner.zip
```

### Step 3: Configure the Runner
Run the configuration script:
```powershell
.\config.cmd --url https://github.com/HarshGosalia05/ByteBrain --token <YOUR_REGISTRATION_TOKEN>
```
> [!IMPORTANT]
> Replace `<YOUR_REGISTRATION_TOKEN>` with the token displayed on your GitHub **New self-hosted runner** page.
> *Note: Registration tokens expire after 1 hour if unused; generate a fresh one from the UI if needed.*

During the interactive prompts:
* **Enter the name of the runner group**: Press `Enter` (default).
* **Enter the name of runner**: Press `Enter` (or enter `CampusX-Runner`).
* **Enter any additional labels**: Enter `Windows` (or press `Enter`).
* **Enter name of work folder**: Press `Enter` (default `_work`).

### Step 4: Run the Runner

You can run the runner in two ways:

#### Option A: Run as a Background Windows Service (Recommended)
This ensures the runner starts automatically whenever your PC boots:
```powershell
.\svc.cmd install
.\svc.cmd start
```
To check service status:
```powershell
.\svc.cmd status
```

#### Option B: Run Interactively in Console (Testing)
```powershell
.\run.cmd
```
You will see:
```
√ Connected to GitHub
Listening for Jobs
```

---

## 4. Normal Developer Workflow

Once the runner is running on your PC, the deployment process is 100% automated:

1. **Developer A or Developer B** commits code and pushes:
   ```powershell
   git add .
   git commit -m "Add new feature"
   git push origin main
   ```
2. **GitHub Actions** detects the push and assigns the `deploy.yml` workflow to your self-hosted Windows runner.
3. **Your Windows PC**:
   - Pulls the exact commit into `C:\actions-runner\_work\ByteBrain\ByteBrain`.
   - Copies `.env.local` safely from `D:\KenexAi\ByteBrain\.env.local`.
   - Rebuilds the updated images using Docker build cache (`docker compose build`).
   - Replaces the running containers in-place (`docker compose up -d --remove-orphans`).
   - Verifies the backend healthcheck and frontend login response.
4. **CampusX is updated live** at `http://localhost:3000` with zero manual intervention.

---

## 5. Worktree Safety Guarantees

Your active development environment at `D:\KenexAi\ByteBrain` is completely safe:
* The GitHub Actions runner executes jobs inside its own isolated directory (`C:\actions-runner\_work\ByteBrain\ByteBrain`).
* No `git reset --hard` or `git clean -fd` is ever run against your active repository.
* Your uncommitted changes, open files in IDE, and scratch scripts will **never** be lost or overwritten by someone else's push.

---

## 6. Safe Zero-Downtime Deployment Flow

If a developer pushes code with a syntax or build error:
1. `docker compose build` fails during the build stage.
2. The workflow halts immediately and flags the commit as **FAILED** on GitHub.
3. The previously running working containers are **never torn down** (because `docker compose down` is not executed).
4. Users continue to access the working version without disruption.

---

## 7. Troubleshooting

### Problem: GitHub Actions says "Waiting for a runner to pick up this job..."
* **Cause**: The self-hosted runner on your PC is offline or not running.
* **Fix**: Ensure the runner process or Windows service is active:
  ```powershell
  Set-Location "C:\actions-runner"
  .\svc.cmd status
  # If stopped, restart it:
  .\svc.cmd start
  ```

### Problem: Docker daemon error during build
* **Cause**: Docker Desktop is not running on your Windows PC.
* **Fix**: Launch **Docker Desktop** and verify `docker ps` returns successfully.

### Problem: Port 3000 or 8000 already in use
* **Cause**: A local development process (`npm run dev` or Python uvicorn) is running directly on the host outside of Docker.
* **Fix**: Stop the host development process to free the ports for the Docker container mappings.

### Problem: Backend container reports "degraded" database
* **Cause**: Remote Supabase PostgreSQL is unreachable due to network connectivity or credentials.
* **Fix**: Verify your network connection and verify `D:\KenexAi\ByteBrain\.env.local` has valid Supabase credentials.
