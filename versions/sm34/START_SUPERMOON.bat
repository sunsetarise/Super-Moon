@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title Super Moon 34 New Universe Prompt Studio
color 0B

set "REQUIRED_PYTHON=C:\Users\zero\AppData\Local\Programs\Python\Python314\python.exe"
set "SM34_REQUIRED_PYTHON=%REQUIRED_PYTHON%"
set "SM32_REQUIRED_PYTHON=%REQUIRED_PYTHON%"

echo ========================================================================
echo   SUPER MOON 34 NEW UNIVERSE PROMPT STUDIO - START
echo ========================================================================
echo.

if not exist "%REQUIRED_PYTHON%" goto :python_missing

"%REQUIRED_PYTHON%" "tools\windows_bootstrap.py" check > "runtime\start-check.json" 2>&1
if errorlevel 1 (
  echo [INFO] Runtime check found a missing or damaged environment.
  echo [INFO] Running automatic dependency/venv repair...
  "%REQUIRED_PYTHON%" "tools\windows_bootstrap.py" setup
  if errorlevel 1 goto :repair_failed
)

if not exist ".venv\Scripts\python.exe" goto :repair_failed
set "VPY=%CD%\.venv\Scripts\python.exe"
set "PYTHONPATH=%CD%;%CD%\supermoon_runtime\src;%PYTHONPATH%"

if not exist "runtime\knowledge_index.sqlite3" (
  echo [INFO] Knowledge index is missing. Building it now...
  "%VPY%" "tools\build_knowledge_index.py"
  if errorlevel 1 echo [WARN] Index build failed; canonical TXT.GZ streaming fallback will be used.
)

if exist "runtime\server-state.json" del /q "runtime\server-state.json" >nul 2>nul

echo [OK] Exact Python installation verified:
echo      %REQUIRED_PYTHON%
"%VPY%" -c "import sys; print('[OK] venv:',sys.version.split()[0], '| base:',getattr(sys,'_base_executable',sys.executable))"
echo.
echo [INFO] Starting backend and browser interface...
echo [INFO] Press Ctrl+C in this window to stop SuperMoon.
echo.
"%VPY%" -m supermoon_studio.launcher
if errorlevel 1 goto :runtime_failed
exit /b 0

:python_missing
echo [ERROR] Required Python is missing:
echo         %REQUIRED_PYTHON%
echo Run SETUP_WINDOWS.bat after restoring that Python installation.
pause
exit /b 2

:repair_failed
echo [ERROR] Automatic runtime repair failed.
echo Review runtime\setup.log and runtime\start-check.json.
pause
exit /b 1

:runtime_failed
echo.
echo [ERROR] SuperMoon backend exited with an error.
if exist "runtime\server-state.json" type "runtime\server-state.json"
pause
exit /b 1
