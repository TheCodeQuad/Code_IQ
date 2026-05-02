@echo off
REM Code_IQ Project Setup and Run Script with Anaconda venv
REM Creates conda environment, installs dependencies and starts both backend and frontend

setlocal enabledelayedexpansion

echo.
echo ========================================
echo   Code_IQ Project Setup ^& Run (Conda)
echo ========================================
echo.

REM Check if running from project root
if not exist "backend" (
    echo Error: backend folder not found. Run this script from project root.
    pause
    exit /b 1
)

if not exist "frontend" (
    echo Error: frontend folder not found. Run this script from project root.
    pause
    exit /b 1
)

REM Setup Anaconda environment
echo [1/5] Setting up Anaconda virtual environment...
set VENV_NAME=codeiq_env

REM Check if conda is available
conda --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Error: Conda not found. Please install Anaconda or Miniconda.
    echo Download from: https://www.anaconda.com/download
    pause
    exit /b 1
)

REM Create conda environment if it doesn't exist
conda env list | find "%VENV_NAME%" >nul
if %errorlevel% neq 0 (
    echo Creating conda environment: %VENV_NAME%
    call conda create -y -n %VENV_NAME% python=3.11
    if %errorlevel% neq 0 (
        echo Error creating conda environment
        pause
        exit /b 1
    )
) else (
    echo Conda environment already exists: %VENV_NAME%
)

echo Activating conda environment...
call conda activate %VENV_NAME%
if %errorlevel% neq 0 (
    echo Error activating conda environment
    pause
    exit /b 1
)
echo [OK] Conda environment activated

echo.

REM Install Backend Dependencies
echo [2/5] Installing backend dependencies in conda environment...
if exist "requirements.txt" (
    pip install -r requirements.txt
    if %errorlevel% neq 0 (
        echo Error installing backend dependencies
        pause
        exit /b 1
    )
    echo [OK] Backend dependencies installed
) else (
    echo [WARN] requirements.txt not found, skipping backend setup
)

echo.

REM Install Frontend Dependencies
echo [3/5] Installing frontend dependencies...
cd frontend
if exist "package.json" (
    call npm install
    if %errorlevel% neq 0 (
        echo Error installing frontend dependencies
        cd ..
        pause
        exit /b 1
    )
    echo [OK] Frontend dependencies installed
) else (
    echo [WARN] package.json not found, skipping frontend setup
)
cd ..

echo.

REM Setup environment files
echo [4/5] Checking environment files...
if not exist ".env" (
    echo [WARN] .env file not found - creating default
    echo BACKEND_URL=http://localhost:8000 > .env
    echo NEXT_PUBLIC_API_URL=http://localhost:8000 >> .env
    echo [INFO] Created .env - update with your settings
)

echo.

REM Start services
echo [5/5] Starting services in conda environment...
echo.
echo Starting Backend (Python FastAPI on port 8000)...
start cmd /k "cd /d %cd% && call conda activate %VENV_NAME% && python backend/main.py"

timeout /t 3 /nobreak

echo Starting Frontend (Next.js on port 3000)...
start cmd /k "cd /d %cd%\frontend && call conda activate %VENV_NAME% && npm run dev"

echo.
echo ========================================
echo   Services Started
echo ========================================
echo Backend:  http://localhost:8000
echo Frontend: http://localhost:3000
echo.
echo Close the terminal windows to stop services.
pause
