@echo off
setlocal
cd /d "%~dp0"
title Build standalone EXE

rem ---------------------------------------------------------------
rem  Builds a standalone exe with PyInstaller.
rem  Output: dist\TargetClicker.exe (single file, no console window,
rem  runs on machines without Python/conda; rename it as you like).
rem  The first run installs PyInstaller over the network.
rem  Want a faster-starting folder build? Replace --onefile with
rem  --onedir below.
rem  ASCII-only on purpose (see run.bat).
rem ---------------------------------------------------------------

set "PY=E:\anconda\envs\point_clicker\python.exe"
set "PYTHONIOENCODING=utf-8"

if not exist "%PY%" goto :no_py
if not exist "main.py" goto :no_main

echo === Step 1/4: check PyInstaller ===
"%PY%" -c "import PyInstaller" >nul 2>nul
if errorlevel 1 goto :install
echo   PyInstaller is already installed.
goto :clean

:install
echo   PyInstaller is missing, installing it with pip (needs internet).
echo   Press Ctrl+C and close this window to cancel.
echo.
pause
"%PY%" -m pip install pyinstaller
if errorlevel 1 goto :pip_fail

:clean
echo.
echo === Step 2/4: remove previous build output ===
if exist "build" rmdir /s /q "build"
if exist "dist" rmdir /s /q "dist"
if exist "TargetClicker.spec" del /q "TargetClicker.spec"

echo.
echo === Step 3/4: building, this can take several minutes ===
"%PY%" -m PyInstaller --noconfirm --clean --onefile --windowed --name TargetClicker main.py
if errorlevel 1 goto :build_fail

echo.
echo === Step 4/4: result ===
if exist "dist\TargetClicker.exe" goto :ok
goto :build_fail

:ok
echo Build finished:
echo   %CD%\dist\TargetClicker.exe
echo Copy that file anywhere and double-click it; Python is not needed.
echo.
pause
exit /b 0

:pip_fail
echo.
echo [ERROR] "pip install pyinstaller" failed. Check the network, retry.
echo.
pause
exit /b 1

:build_fail
echo.
echo [ERROR] Build failed. Please send the messages above to the assistant.
echo.
pause
exit /b 1

:no_py
echo.
echo [ERROR] Python interpreter not found:
echo         %PY%
echo.
pause
exit /b 1

:no_main
echo.
echo [ERROR] main.py was not found in:
echo         %CD%
echo.
pause
exit /b 1
