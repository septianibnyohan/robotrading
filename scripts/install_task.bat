@echo off
cd /d "%~dp0"

:: Check for admin privileges
net session >nul 2>&1
if %errorLevel% == 0 (
    goto :run
) else (
    echo Requesting administrative privileges to set up Windows Task Scheduler...
    powershell -Command "Start-Process -FilePath '%~dpnx0' -Verb RunAs"
    exit /b
)

:run
echo =======================================================
echo Installing RoboBTC Harvester Scheduled Task
echo =======================================================
powershell -ExecutionPolicy Bypass -File "setup_task.ps1"
echo.
echo Setup finished. Check for any errors above.
echo You can view the task in the Windows "Task Scheduler" app.
pause
