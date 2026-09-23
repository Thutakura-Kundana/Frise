@echo off

echo ==========================================
echo   Starting Frise
echo ==========================================
echo.

echo Starting Backend...
start "Frise Backend" cmd /k "cd /d "%~dp0" && call backend\venv\Scripts\activate.bat && python -m backend.main"

timeout /t 2 /nobreak >nul

echo Starting Frontend...
start "Frise Frontend" cmd /k "cd /d "%~dp0frontend" && npm run dev"

echo.
echo ==========================================
echo   Frise is starting...
echo ==========================================
echo.
pause