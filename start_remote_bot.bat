@echo off
echo ========================================
echo Starting CC Release Monitor with Remote Approval
echo ========================================
echo.

:: Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.9 or higher
    pause
    exit /b 1
)

:: Activate virtual environment if it exists
if exist venv\Scripts\activate.bat (
    echo Activating virtual environment...
    call venv\Scripts\activate.bat
)

:: Run the bot with remote approval system
echo Starting bot with remote approval system...
echo.
echo The bot will start both:
echo 1. Release monitoring for Claude Code
echo 2. IPC server for remote approval (port 8765)
echo.
echo Press Ctrl+C to stop the bot
echo ========================================
echo.

python remote_bot.py

pause