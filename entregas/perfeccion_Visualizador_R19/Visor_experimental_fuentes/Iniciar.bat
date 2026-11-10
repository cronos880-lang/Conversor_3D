@echo off
setlocal
cd /d "%~dp0"
py -3.12 -V >nul 2>&1
if errorlevel 1 (
 echo Esta copia necesita Python 3.12 de 64 bits, como R7.
 pause
 exit /b 1
)
set "PYTHONIOENCODING=utf-8"
py -3.12 arrancar.py
if errorlevel 1 pause
