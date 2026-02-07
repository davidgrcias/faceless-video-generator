@echo off
echo ========================================
echo  Faceless Video Generator - Starting
echo ========================================
echo.

REM Start backend
echo Starting backend on http://localhost:8000 ...
start "FCG-Backend" cmd /k "cd /d %~dp0backend && venv\Scripts\activate.bat && uvicorn main:app --reload --port 8000"

REM Wait a moment for backend to start
timeout /t 3 /nobreak >nul

REM Start frontend
echo Starting frontend on http://localhost:5173 ...
start "FCG-Frontend" cmd /k "cd /d %~dp0frontend && npm run dev"

REM Wait a moment then open browser
timeout /t 3 /nobreak >nul
echo.
echo Opening browser...
start http://localhost:5173

echo.
echo ========================================
echo  App is running!
echo  Frontend: http://localhost:5173
echo  Backend:  http://localhost:8000
echo  API docs: http://localhost:8000/docs
echo ========================================
