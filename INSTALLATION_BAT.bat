@echo off
REM Code_IQ Project Setup Script with Anaconda venv
REM Creates conda environment, installs dependencies, configures llama-cpp, and downloads model

setlocal enabledelayedexpansion

echo.
echo ========================================
echo   Code_IQ Setup with Anaconda (Install)
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
set CONDA_BAT=

REM Resolve conda.bat even when Conda is not initialized in PATH
if defined CONDA_EXE (
    if exist "%CONDA_EXE%" set CONDA_BAT=%CONDA_EXE%
)
if not defined CONDA_BAT (
    if exist "%UserProfile%\anaconda3\condabin\conda.bat" set CONDA_BAT=%UserProfile%\anaconda3\condabin\conda.bat
)
if not defined CONDA_BAT (
    if exist "%UserProfile%\miniconda3\condabin\conda.bat" set CONDA_BAT=%UserProfile%\miniconda3\condabin\conda.bat
)
if not defined CONDA_BAT (
    if exist "C:\ProgramData\anaconda3\condabin\conda.bat" set CONDA_BAT=C:\ProgramData\anaconda3\condabin\conda.bat
)
if not defined CONDA_BAT (
    if exist "C:\ProgramData\miniconda3\condabin\conda.bat" set CONDA_BAT=C:\ProgramData\miniconda3\condabin\conda.bat
)
if not defined CONDA_BAT (
    where conda >nul 2>&1
    if not errorlevel 1 set CONDA_BAT=conda
)

if not defined CONDA_BAT (
    echo Error: Conda not found. Please install Anaconda or Miniconda.
    echo If Conda is installed, run this script from Anaconda Prompt, or add condabin to PATH.
    echo Download from: https://www.anaconda.com/download
    pause
    exit /b 1
)

call "%CONDA_BAT%" --version >nul 2>&1
if errorlevel 1 (
    echo Error: Conda was found but is not runnable from this shell.
    echo Try opening Anaconda Prompt and run this script again.
    pause
    exit /b 1
)
echo [OK] Conda detected: %CONDA_BAT%

REM Accept Conda Terms of Service for default channels (required on newer Conda)
echo Checking Conda channel Terms of Service...
call "%CONDA_BAT%" tos accept --override-channels --channel https://repo.anaconda.com/pkgs/main >nul 2>&1
call "%CONDA_BAT%" tos accept --override-channels --channel https://repo.anaconda.com/pkgs/r >nul 2>&1

REM Create conda environment if it doesn't exist
call "%CONDA_BAT%" env list | find "%VENV_NAME%" >nul
if errorlevel 1 (
    echo Creating conda environment: %VENV_NAME% with Python 3.11...
    call "%CONDA_BAT%" create -y -n %VENV_NAME% python=3.11
    if errorlevel 1 (
        echo Error creating conda environment
        pause
        exit /b 1
    )
    echo [OK] Conda environment created
) else (
    echo [OK] Conda environment already exists: %VENV_NAME%
)

echo Activating conda environment...
call "%CONDA_BAT%" activate %VENV_NAME%
if errorlevel 1 (
    echo Error activating conda environment
    echo Try running this script in Anaconda Prompt.
    pause
    exit /b 1
)
echo [OK] Conda environment activated

echo.

REM Install Backend Dependencies
echo [2/5] Installing Python backend dependencies...
if exist "requirements.txt" (
    pip install -r requirements.txt
    if errorlevel 1 (
        echo Error installing backend dependencies
        pause
        exit /b 1
    )
    echo [OK] Backend dependencies installed
) else (
    echo [WARN] requirements.txt not found
)

echo.

REM Detect hardware and install llama-cpp-python
echo [3/5] Detecting hardware and installing llama-cpp-python...
set HAS_GPU=0
where nvidia-smi >nul 2>&1
if not errorlevel 1 (
    nvidia-smi >nul 2>&1
    if not errorlevel 1 set HAS_GPU=1
)

if "%HAS_GPU%"=="1" (
    echo [INFO] NVIDIA GPU detected. Installing CUDA build of llama-cpp-python...
    pip uninstall -y llama-cpp-python >nul 2>&1
    pip install --upgrade llama-cpp-python --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cu124
    if errorlevel 1 (
        echo [WARN] CUDA wheel install failed. Falling back to CPU build...
        pip install --upgrade llama-cpp-python
        if errorlevel 1 (
            echo Error installing llama-cpp-python
            pause
            exit /b 1
        )
        set HAS_GPU=0
    )
) else (
    echo [INFO] No NVIDIA GPU detected. Installing CPU build of llama-cpp-python...
    pip install --upgrade llama-cpp-python
    if errorlevel 1 (
        echo Error installing llama-cpp-python
        pause
        exit /b 1
    )
)
echo [OK] llama-cpp-python installed

echo.

REM Download GGUF model based on hardware
echo [4/5] Downloading Qwen Coder GGUF model to models folder...
if not exist "models" mkdir models

if "%HAS_GPU%"=="1" (
    set MODEL_FILE=Qwen2.5-Coder-14B-Instruct-Q4_K_M.gguf
    set MODEL_URL=https://huggingface.co/bartowski/Qwen2.5-Coder-14B-Instruct-GGUF/resolve/main/Qwen2.5-Coder-14B-Instruct-Q4_K_M.gguf?download=true
    echo [INFO] GPU mode selected: !MODEL_FILE!
) else (
    set MODEL_FILE=Qwen2.5-Coder-1.5B-Instruct-Q4_K_M.gguf
    set MODEL_URL=https://huggingface.co/bartowski/Qwen2.5-Coder-1.5B-Instruct-GGUF/resolve/main/Qwen2.5-Coder-1.5B-Instruct-Q4_K_M.gguf?download=true
    echo [INFO] CPU mode selected: !MODEL_FILE!
)

if exist "models\!MODEL_FILE!" (
    echo [OK] Model already exists: models\!MODEL_FILE!
) else (
    echo Downloading !MODEL_FILE! ...
    powershell -NoProfile -ExecutionPolicy Bypass -Command "Invoke-WebRequest -Uri '!MODEL_URL!' -OutFile 'models\!MODEL_FILE!'"
    if errorlevel 1 (
        echo Error downloading model file
        pause
        exit /b 1
    )
    echo [OK] Model downloaded: models\!MODEL_FILE!
)

echo.

REM Install Frontend Dependencies
echo [5/5] Installing Node.js frontend dependencies...
cd frontend
if exist "package.json" (
    call npm install
    if errorlevel 1 (
        echo Error installing frontend dependencies
        cd ..
        pause
        exit /b 1
    )
    echo [OK] Frontend dependencies installed
) else (
    echo [WARN] package.json not found
)
cd ..

echo.
echo ========================================
echo   Installation Complete!
echo ========================================
echo.
echo Conda environment: %VENV_NAME%
if "%HAS_GPU%"=="1" (
    echo Runtime mode: GPU
) else (
    echo Runtime mode: CPU
)
echo Model path: models\!MODEL_FILE!
echo.
echo Next steps:
echo   1. Run "run_project_conda.bat" to start both services
echo   2. Or activate manually: conda activate %VENV_NAME%
echo   3. Then run backend: python backend/main.py
echo   4. In another terminal: cd frontend ^&^& npm run dev
echo.
pause
