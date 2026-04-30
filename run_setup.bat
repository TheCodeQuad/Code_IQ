@echo off
cd /d C:\BIA6\CodeIQ\Code_IQ
python setup_ckg_simple.py
echo.
echo Listing created directories and files:
dir /s frontend\app\api\graphs\ckg 2>nul
