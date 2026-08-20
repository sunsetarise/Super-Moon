@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title Super Moon 34 New Universe Prompt Studio - Full Audit
set "REQUIRED_PYTHON=C:\Users\zero\AppData\Local\Programs\Python\Python314\python.exe"
set "SM34_REQUIRED_PYTHON=%REQUIRED_PYTHON%"
set "SM32_REQUIRED_PYTHON=%REQUIRED_PYTHON%"

if not exist "%REQUIRED_PYTHON%" (
  echo [ERROR] Required Python is missing: %REQUIRED_PYTHON%
  pause
  exit /b 2
)

"%REQUIRED_PYTHON%" "tools\windows_bootstrap.py" check >nul 2>nul
if errorlevel 1 (
  echo [INFO] Environment is not healthy. Running setup first...
  call SETUP_WINDOWS.bat
  if errorlevel 1 exit /b 1
)

set "VPY=%CD%\.venv\Scripts\python.exe"
set "PYTHONPATH=%CD%;%CD%\supermoon_runtime\src;%PYTHONPATH%"

echo [1/4] Running package audit...
"%VPY%" "tools\audit_package.py"
if errorlevel 1 goto :fail

echo [2/4] Running inherited plus SM34 New Universe regression suite...
"%VPY%" -m pytest -q tests supermoon_runtime\tests
if errorlevel 1 goto :fail

echo [3/4] Running integrated PDF/runtime self-test...
"%VPY%" -m supermoon_studio.self_test
if errorlevel 1 goto :fail

echo [4/4] Checking installed dependency graph...
"%VPY%" -m pip --isolated check
if errorlevel 1 goto :fail

echo.
echo [OK] Full audit passed.
echo Audit record: runtime\FULL_AUDIT_REPORT.json
pause
exit /b 0

:fail
echo.
echo [ERROR] Full audit failed. Review the console and runtime logs.
pause
exit /b 1
