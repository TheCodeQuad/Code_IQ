@echo off
setlocal enabledelayedexpansion

echo.
echo ========================================
echo        CodeIQ Setup ^& Run Script
echo ========================================
echo.

REM ----------------------------------------
REM CHECK PROJECT STRUCTURE
REM ----------------------------------------
if not exist "backend" (
    echo [ERROR] backend folder not found!
    pause
    exit /b 1
)

if not exist "frontend" (
    echo [ERROR] frontend folder not found!
    pause
    exit /b 1
)

REM ----------------------------------------
REM CONFIG
REM ----------------------------------------
set VENV_NAME=codeiq

REM Detect Conda install
if exist "%USERPROFILE%\anaconda3\Scripts\activate.bat" (
    set CONDA_PATH=%USERPROFILE%\anaconda3
) else if exist "%USERPROFILE%\miniconda3\Scripts\activate.bat" (
    set CONDA_PATH=%USERPROFILE%\miniconda3
) else (
    echo [ERROR] Conda not found!
    echo Install from: https://www.anaconda.com/download
    pause
    exit /b 1
)

echo [INFO] Using Conda at: %CONDA_PATH%

REM ----------------------------------------
REM CREATE ENV IF NOT EXISTS
REM ----------------------------------------
call "%CONDA_PATH%\Scripts\activate.bat"

conda env list | find "%VENV_NAME%" >nul
if %errorlevel% neq 0 (
    echo [INFO] Creating conda environment: %VENV_NAME%
    call conda create -y -n %VENV_NAME% python=3.11
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to create environment
        pause
        exit /b 1
    )
)

REM ----------------------------------------
REM ACTIVATE ENV
REM ----------------------------------------
echo [INFO] Activating environment...
call "%CONDA_PATH%\Scripts\activate.bat" %VENV_NAME%

REM ----------------------------------------
REM INSTALL BACKEND DEPENDENCIES
REM ----------------------------------------
echo.
echo [1/3] Installing backend dependencies...

if exist "requirements.txt" (
    pip install -r requirements.txt
) else (
    echo [WARN] No requirements.txt found
)

REM ----------------------------------------
REM INSTALL FRONTEND DEPENDENCIES
REM ----------------------------------------
echo.
echo [2/3] Installing frontend dependencies...

cd frontend
if exist "package.json" (
    call npm install
) else (
    echo [WARN] No package.json found
)
cd ..

REM ----------------------------------------
REM START BACKEND
REM ----------------------------------------
echo.
echo [3/3] Starting backend...

start "CodeIQ Backend" cmd /k ^
"cd /d %cd% && ^
CALL %CONDA_PATH%\Scripts\activate.bat %VENV_NAME% && ^
python -m uvicorn backend.main:app --reload --port 8000"

timeout /t 3 >nul

REM ----------------------------------------
REM START FRONTEND
REM ----------------------------------------
echo Starting frontend...

start "CodeIQ Frontend" cmd /k ^
"cd /d %cd%\frontend && ^
call npm run dev"

REM ----------------------------------------
REM DONE
REM ----------------------------------------
echo.
echo ========================================
echo        CodeIQ is Running 🚀
echo ========================================
echo Backend  : http://localhost:8000
echo API Docs : http://localhost:8000/docs
echo Frontend : http://localhost:3000
echo ========================================
echo.

pause