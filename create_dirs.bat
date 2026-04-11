@echo off
echo === Setting up CKG (Program Knowledge Graph) ===
cd /d C:\BIA6\CodeIQ\Code_IQ

echo.
echo Running setup script...
python setup_ckg_simple.py

echo.
echo === Setup Complete ===
echo.
echo IMPORTANT: Restart your frontend server!
echo   cd frontend
echo   npm run dev
echo.
pause
