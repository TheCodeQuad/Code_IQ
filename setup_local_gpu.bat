@echo off
REM Windows Setup Script for Local GPU Fine-tuning
REM Run this from your Code_IQ directory

echo ========================================
echo Code_IQ Local GPU Fine-tuning Setup
echo ========================================
echo.

REM Check Python
echo [1/5] Checking Python installation...
python --version
if errorlevel 1 (
    echo ERROR: Python not found! Install Python 3.10+ first.
    exit /b 1
)
echo.

REM Create virtual environment
echo [2/5] Creating virtual environment...
if exist venv_codeiq (
    echo Virtual environment already exists. Activating...
) else (
    python -m venv venv_codeiq
    echo Virtual environment created.
)
echo.

REM Activate virtual environment
echo [3/5] Activating virtual environment...
call venv_codeiq\Scripts\activate.bat
if errorlevel 1 (
    echo ERROR: Failed to activate virtual environment.
    exit /b 1
)
echo.

REM Install PyTorch with CUDA
echo [4/5] Installing PyTorch with CUDA 11.8...
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
if errorlevel 1 (
    echo ERROR: Failed to install PyTorch.
    exit /b 1
)
echo.

REM Install dependencies
echo [5/5] Installing other dependencies...
pip install --upgrade transformers accelerate "datasets>=2.19.0,<3.0.0" peft bitsandbytes
pip install nltk rouge-score sacrebleu tree-sitter codebleu
if errorlevel 1 (
    echo ERROR: Failed to install dependencies.
    exit /b 1
)
echo.

REM Download NLTK data
echo Downloading NLTK data...
python -m nltk.downloader wordnet omw-1.4
echo.

REM Verify installation
echo ========================================
echo Verifying installation...
echo ========================================
python -c "import torch; print(f'PyTorch version: {torch.__version__}'); print(f'CUDA available: {torch.cuda.is_available()}'); print(f'GPU: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else \"Not found\"}')"
echo.

echo ========================================
echo Setup Complete!
echo ========================================
echo.
echo Next steps:
echo 1. Read: LOCAL_GPU_FINETUNING_GUIDE.md
echo 2. Edit: scripts/fine_tune_local_gpu.py (adjust for your GPU)
echo 3. Run:  python scripts/fine_tune_local_gpu.py
echo.
echo To activate the environment later, run:
echo   venv_codeiq\Scripts\activate.bat (Windows)
echo   source venv_codeiq/bin/activate  (Linux/Mac)
echo.

pause
