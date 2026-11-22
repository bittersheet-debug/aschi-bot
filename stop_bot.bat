@echo off
echo Menghentikan proses ASCHI BOT dan watchdog...
taskkill /F /IM python.exe /FI "WINDOWTITLE eq ASCHI BOT*" >nul 2>&1
taskkill /F /FI "COMMANDLINE eq *bot.py*" >nul 2>&1
taskkill /F /FI "COMMANDLINE eq *watchdog_runner.py*" >nul 2>&1
echo Selesai. ASCHI BOT telah dihentikan.
pause
