@echo off
setlocal
cd /d "%~dp0"
title Create Desktop Shortcut

rem Copies the .lnk shortcut of this folder to the desktop.
rem Double-click this file once. ASCII-only on purpose (see run.bat).

if not exist "*.lnk" goto :no_lnk
for %%F in (*.lnk) do set "LNK=%%~nxF"

set "DESK="
for /f "tokens=2,*" %%A in ('reg query "HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders" /v Desktop 2^>nul') do set "DESK=%%B"
call set "DESK=%DESK%"
if not defined DESK set "DESK=%USERPROFILE%\Desktop"

copy /y "%LNK%" "%DESK%\" >nul 2>nul
if errorlevel 1 goto :fail

echo Desktop shortcut created:
echo   %DESK%\%LNK%
echo.
echo From now on, double-click that desktop icon to start the app
echo (no console window will appear).
pause
exit /b 0

:no_lnk
echo.
echo [ERROR] No .lnk file found in:
echo         %CD%
echo         This script must stay in the project folder.
echo.
pause
exit /b 1

:fail
echo.
echo [ERROR] Copy to desktop failed. Target folder:
echo         %DESK%
echo         Please copy the .lnk to your desktop manually.
echo.
pause
exit /b 1
