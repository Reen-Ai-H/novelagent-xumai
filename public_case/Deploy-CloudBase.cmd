@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Deploy-CloudBase.ps1" %*
exit /b %ERRORLEVEL%
