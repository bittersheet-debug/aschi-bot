@echo off
cd /d "%~dp0"
echo ========================================================
echo   MEMASANG ASCHI BOT KE WINDOWS STARTUP (AUTO-BOOT)
echo ========================================================
echo.

set TARGET_DIR=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup
set VBS_SOURCE=%~dp0start_hidden.vbs

if not exist "%VBS_SOURCE%" (
    echo Error: start_hidden.vbs tidak ditemukan.
    pause
    exit /b 1
)

echo Membuat shortcut otomatis di Windows Startup...
powershell -Command "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut('%TARGET_DIR%\ASCHI_BOT_AutoStart.lnk'); $s.TargetPath = 'wscript.exe'; $s.Arguments = '\"%VBS_SOURCE%\"'; $s.WorkingDirectory = '%~dp0'; $s.Save()"

if %errorlevel% equ 0 (
    echo.
    echo [BERHASIL] ASCHI BOT sekarang otomatis menyala di background
    echo setiap kali Windows dinyalakan atau restart!
    echo.
    echo Lokasi startup:
    echo %TARGET_DIR%\ASCHI_BOT_AutoStart.lnk
) else (
    echo [GAGAL] Terjadi kesalahan saat membuat shortcut startup.
)

echo.
pause
