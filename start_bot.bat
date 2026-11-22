@echo off
title ASCHI BOT - 24/7 KEEP-ALIVE SUPERVISOR
color 0A
cd /d "%~dp0"
echo ========================================================
echo        ASCHI BOT - ASCHEN EVENT ORGANIZER
echo        24/7 KEEP-ALIVE AUTO-RESTART SUPERVISOR
echo ========================================================
echo.
python watchdog_runner.py
pause
