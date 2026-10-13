@echo off
REM PandorumLLM - starts the panel without the .exe.
REM Kept so an antivirus false positive on the launcher can never leave you with no
REM way in: this file is plain text and does exactly what you can read here.
setlocal EnableDelayedExpansion
cd /d "%~dp0"

if not exist "fleet-panel.py" (
  echo [X] fleet-panel.py is not in this folder: %CD%
  pause & exit /b 1
)

set "PY="
where pythonw >nul 2>&1 && set "PY=pythonw"
if not defined PY ( where py >nul 2>&1 && set "PY=py" )
if not defined PY ( where python >nul 2>&1 && set "PY=python" )
if not defined PY (
  echo [X] Python was not found on PATH. Install it, or tick "Add to PATH" if you have.
  pause & exit /b 1
)

del /q "panel-port.txt" >nul 2>&1
echo Starting the panel with %PY% ...
start "" /b %PY% "fleet-panel.py"

REM the panel writes panel-port.txt once it has bound a port
for /l %%i in (1,1,60) do (
  if exist "panel-port.txt" goto opened
  >nul ping -n 2 127.0.0.1
)
echo.
echo [X] The panel did not answer within a minute. Look in:
echo       logs\STARTUP-CRASH.log   any startup failure lands here
echo       logs\panel.log           the normal startup log
pause & exit /b 1

:opened
set /p PORT=<"panel-port.txt"
echo Panel is up on port !PORT! - opening your browser.
start "" "http://localhost:!PORT!/"
exit /b 0
