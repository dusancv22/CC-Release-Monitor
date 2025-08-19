@echo off
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

REM Start the bot
C:\Users\Dusan\miniconda3\python.exe simple_bot.py

echo.
echo Bot has stopped.
echo.
pause