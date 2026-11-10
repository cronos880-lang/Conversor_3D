@echo off
setlocal
cd /d "%~dp0"
call "..\Instalar_Entorno_R19.bat"
exit /b %ERRORLEVEL%
