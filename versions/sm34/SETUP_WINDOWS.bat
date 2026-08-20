@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title Super Moon 34 New Universe Prompt Studio - Audited Setup
color 0B

set "REQUIRED_PYTHON=C:\Users\zero\AppData\Local\Programs\Python\Python314\python.exe"
set "SM34_REQUIRED_PYTHON=%REQUIRED_PYTHON%"
set "SM32_REQUIRED_PYTHON=%REQUIRED_PYTHON%"

echo ========================================================================
echo   SUPER MOON 34 NEW UNIVERSE PROMPT STUDIO - FULL AUDITED SETUP
echo   Required runtime: CPython 3.14 x64
echo ========================================================================
echo.
echo [CHECK] Required Python:
echo         %REQUIRED_PYTHON%

if not exist "%REQUIRED_PYTHON%" goto :python_missing

"%REQUIRED_PYTHON%" -c "import sys,struct; assert sys.implementation.name=='cpython'; assert sys.version_info[:2]==(3,14); assert struct.calcsize('P')*8==64; print('[OK] CPython',sys.version.split()[0],str(struct.calcsize('P')*8)+'-bit'); print('[OK] executable:',sys.executable)"
if errorlevel 1 goto :python_invalid

"%REQUIRED_PYTHON%" "tools\windows_bootstrap.py" setup %*
if errorlevel 1 goto :setup_failed

echo.
echo ========================================================================
echo   SETUP COMPLETE
echo ========================================================================
echo Run START_SUPERMOON.bat to launch the application.
echo For the complete inherited plus SM34 verification, run RUN_FULL_AUDIT.bat.
echo Logs: runtime\setup.log
pause
exit /b 0

:python_missing
echo.
echo [ERROR] Python 3.14 was not found at the exact path you configured:
echo         %REQUIRED_PYTHON%
echo.
echo PATH diagnostics:
where python.exe 2>nul
where py.exe 2>nul
echo.
echo The setup intentionally does NOT silently switch to another Python.
echo Correct the installation at the path above, then rerun this BAT.
pause
exit /b 2

:python_invalid
echo.
echo [ERROR] The executable exists but is not 64-bit CPython 3.14.
echo Required: %REQUIRED_PYTHON%
pause
exit /b 3

:setup_failed
echo.
echo [ERROR] Setup failed. Review runtime\setup.log.
echo Source compilation is disabled for Python 3.14 dependencies.
echo Rust/MSVC is not required for the normal installation path.
pause
exit /b 1
