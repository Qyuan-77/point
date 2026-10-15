@echo off
setlocal
cd /d "%~dp0"
title Target Color Auto Clicker

rem ---------------------------------------------------------------
rem  Launcher (console version: keeps the window open on errors).
rem  Keep this file ASCII-only with CRLF line endings.
rem  Reason: cmd.exe mis-parses non-ASCII batch text, and a mid-file
rem  "chcp" switch makes cmd lose sync with the file offsets.
rem  For a silent start with no console window, double-click the
rem  .lnk shortcut in this folder instead (it runs pythonw.exe).
rem ---------------------------------------------------------------

set "PY=E:\anconda\envs\point_clicker\python.exe"
set "PYTHONIOENCODING=utf-8"
rem The app sets DPI awareness itself before Qt starts, so Qt logs a
rem harmless "SetProcessDpiAwarenessContext() failed: Access denied".
rem Mute just that Qt category to keep this console clean.
set "QT_LOGGING_RULES=qt.qpa.window=false"

if not exist "main.py" goto :no_main
if exist "%PY%" goto :launch

echo.
echo [ERROR] Python interpreter not found:
echo         %PY%
echo         Create the conda env "point_clicker" first, or open this
echo         file with Notepad and fix the PY path.
echo.
pause
exit /b 1

:no_main
echo.
echo [ERROR] main.py was not found in the current folder:
echo         %CD%
echo         Keep this .bat next to main.py.
echo.
pause
exit /b 1

:launch
echo Starting Target Color Auto Clicker ...
echo   interpreter : %PY%
echo   work folder : %CD%
echo   how to quit : press F8, or close the app window
echo.
"%PY%" main.py
set "RC=%ERRORLEVEL%"
if "%RC%"=="0" goto :done

echo.
echo [ERROR] main.py exited with code %RC%
echo         Please send the messages above to the assistant.
echo.
pause
exit /b %RC%

:done
exit /b 0
