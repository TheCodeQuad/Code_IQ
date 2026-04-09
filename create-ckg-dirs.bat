@echo off
REM Create directories
echo Creating directories...
if not exist "frontend\app\api\graphs\ckg" mkdir "frontend\app\api\graphs\ckg"
if not exist "frontend\app\api\graphs\ckg\stats" mkdir "frontend\app\api\graphs\ckg\stats"
if not exist "frontend\app\api\graphs\ckg\subgraph" mkdir "frontend\app\api\graphs\ckg\subgraph"

echo Directories created. Now execute the Node.js setup script:
echo node setup-ckg.js

REM Alternatively, if you want to run it in the same batch:
REM node "%CD%\setup-ckg.js"

echo.
echo To verify, run:
echo dir /s frontend\app\api\graphs\ckg
