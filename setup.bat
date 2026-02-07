@echo off
echo ========================================
echo  Faceless Video Generator - Setup
echo ========================================
echo.

REM Check Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found. Install from https://python.org
    pause
    exit /b 1
)

REM Check Node
node --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Node.js not found. Install from https://nodejs.org
    pause
    exit /b 1
)

REM Check FFmpeg
ffmpeg -version >nul 2>&1
if %errorlevel% neq 0 (
    echo [WARNING] FFmpeg not found. Install with: winget install Gyan.FFmpeg
    echo           Or download from https://www.gyan.dev/ffmpeg/builds/
    echo.
)

echo [1/4] Creating Python virtual environment...
cd backend
python -m venv venv
call venv\Scripts\activate.bat

echo [2/4] Installing Python dependencies...
pip install -r requirements.txt

echo [3/4] Installing Node dependencies...
cd ..\frontend
call npm install

echo [4/4] Setup complete!
echo.
echo ========================================
echo  To start the app, run: start.bat
echo ========================================
pause
