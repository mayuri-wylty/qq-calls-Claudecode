@echo off
chcp 65001 >nul
set "ROOT=%~dp0"
set "SCRIPT=%ROOT%Start-A5.ps1"

echo Starting A5 services...
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT%"
set "EXIT_CODE=%ERRORLEVEL%"

if not "%EXIT_CODE%"=="0" (
  echo.
  echo Start failed. See logs\launcher.log
  pause
  exit /b %EXIT_CODE%
)

echo.
echo A5 startup command finished. See logs\launcher.log for details.
timeout /t 3 /nobreak >nul
exit /b 0
