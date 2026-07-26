@echo off
setlocal
:: ================================================================
::  force-stop.bat - the last resort.
::
::  Normally you close PandorumLLM with Exit in the panel, which stops
::  the servers on its way out. Use this only when the panel will not
::  open or will not answer.
::
::  Only processes started from THIS folder are stopped, so a
::  llama-server you run yourself from elsewhere is left alone.
::  No administrator rights are needed - the fleet does not use them.
:: ================================================================

set "STACK=%~dp0"
echo Stopping everything PandorumLLM started from:
echo    %STACK%
echo.

pwsh -NoProfile -ExecutionPolicy Bypass -Command "$root=$env:STACK; $n=0; Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -and $_.CommandLine.Contains($root) } | ForEach-Object { try { Stop-Process -Id $_.ProcessId -Force -ErrorAction Stop; $n++ } catch {} }; Get-Process -Name PandorumLLM -ErrorAction SilentlyContinue | Where-Object { $_.Path -and $_.Path.StartsWith($root) } | ForEach-Object { try { Stop-Process -Id $_.Id -Force -ErrorAction Stop; $n++ } catch {} }; Write-Host ('Stopped ' + $n + ' process(es).')"

echo.
pause
