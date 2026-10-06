@echo off
setlocal
cd /d "%~dp0scanner-cli"
if errorlevel 1 (
    echo [ERROR] Could not open the scanner-cli folder.
    pause
    exit /b 1
)
if not exist "%~dp0.venv\Scripts\python.exe" (
    echo [ERROR] Python was not found in the parent .venv\Scripts folder.
    pause
    exit /b 1
)
"%~dp0.venv\Scripts\python.exe" main.py %*
set "scan_exit=%ERRORLEVEL%"
if not "%scan_exit%"=="0" echo [ERROR] Scanner CLI exited with code %scan_exit%.
pause
exit /b %scan_exit%
