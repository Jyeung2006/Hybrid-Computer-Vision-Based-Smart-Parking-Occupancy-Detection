@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Python environment missing. Follow QUICK_START.md installation instructions first.
  pause
  exit /b 2
)
".venv\Scripts\python.exe" main.py %*
set "demo_exit=%errorlevel%"
echo.
if not "%demo_exit%"=="0" echo Demo ended with status %demo_exit%. See the message above.
pause
exit /b %demo_exit%
