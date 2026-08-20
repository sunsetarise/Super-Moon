@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title Super Moon 34 New Universe Prompt Studio - Installation Doctor
set "REQUIRED_PYTHON=C:\Users\zero\AppData\Local\Programs\Python\Python314\python.exe"
set "SM34_REQUIRED_PYTHON=%REQUIRED_PYTHON%"
set "SM32_REQUIRED_PYTHON=%REQUIRED_PYTHON%"

if not exist "%REQUIRED_PYTHON%" (
  echo [FAIL] Required Python not found:
  echo        %REQUIRED_PYTHON%
  echo.
  echo PATH diagnostics:
  where python.exe 2>nul
  where py.exe 2>nul
  pause
  exit /b 2
)

"%REQUIRED_PYTHON%" "tools\windows_bootstrap.py" doctor
set "RC=%ERRORLEVEL%"
echo.
if "%RC%"=="0" (
  echo [OK] Installation doctor passed.
) else (
  echo [FAIL] Installation doctor found an issue. Run SETUP_WINDOWS.bat.
)
echo Report/log: runtime\setup.log
pause
exit /b %RC%
