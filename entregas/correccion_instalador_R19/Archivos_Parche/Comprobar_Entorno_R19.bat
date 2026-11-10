@echo off
setlocal
cd /d "%~dp0"
chcp 65001 >nul
set "PYTHONIOENCODING=utf-8"
set "PYTHONDONTWRITEBYTECODE=1"
set "OPENBLAS_NUM_THREADS=1"
set "OMP_NUM_THREADS=1"
set "MKL_NUM_THREADS=1"
py -3.12 -V >nul 2>&1
if errorlevel 1 (
 echo Se necesita Python 3.12 de 64 bits.
 pause
 exit /b 1
)
py -3.12 -u "Preparar_Entorno_R19.py" --comprobar
set "RESULTADO=%ERRORLEVEL%"
if not "%RESULTADO%"=="0" goto fallo
echo.
echo Entorno comprobado. Abriendo el Visor R19...
call "Iniciar_R19.bat"
exit /b %ERRORLEVEL%
:fallo
echo No se ha confirmado el entorno. Revisa el registro indicado arriba.
pause
exit /b %RESULTADO%
