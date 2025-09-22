@echo off
setlocal enabledelayedexpansion
title CC Release Monitor Bot

echo.
echo ====================================
echo   CC Release Monitor Bot Launcher
echo ====================================
echo.
echo Starting Claude Code Release Monitor...
echo.
echo Bot will monitor: anthropics/claude-code
echo Check interval: 30 minutes
echo.
echo Press Ctrl+C to stop the bot
echo.

REM Change to the script directory
cd /d "%~dp0"

REM Pick the Python interpreter (prefer local venv)
set "PYTHON_PATH=%~dp0venv\Scripts\python.exe"
if not exist "!PYTHON_PATH!" set "PYTHON_PATH=python"

"!PYTHON_PATH!" simple_bot.py
set "EXIT_CODE=%ERRORLEVEL%"

echo.
if "%EXIT_CODE%"=="0" (
    echo Bot has stopped.
) else (
    echo Bot exited with error code %EXIT_CODE%.
)
echo.
pause
endlocal
