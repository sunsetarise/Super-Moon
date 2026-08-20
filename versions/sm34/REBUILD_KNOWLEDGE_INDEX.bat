@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title Super Moon 34 New Universe Prompt Studio - Rebuild Knowledge Index
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
  echo [INFO] Repairing Python environment before index rebuild...
  "%REQUIRED_PYTHON%" "tools\windows_bootstrap.py" setup
  if errorlevel 1 (
    echo [ERROR] Environment repair failed. See runtime\setup.log.
    pause
    exit /b 1
  )
)

set "VPY=%CD%\.venv\Scripts\python.exe"
set "PYTHONPATH=%CD%;%CD%\supermoon_runtime\src;%PYTHONPATH%"
echo [INFO] Rebuilding full SM34 New Universe knowledge index...
"%VPY%" "tools\build_knowledge_index.py" --force
if errorlevel 1 (
  echo [ERROR] Knowledge index rebuild failed.
  pause
  exit /b 1
)
echo [OK] Knowledge index rebuilt successfully.
pause
exit /b 0
