@echo off
setlocal
cd /d "%~dp0"
echo Preparando entorno independiente EXPERIMENTAL del Visor STL V4.0 R4...
py -3.13 -V >nul 2>&1
if not errorlevel 1 (
  set "PYTHON=py -3.13"
) else (
  py -3.12 -V >nul 2>&1
  if not errorlevel 1 (
    set "PYTHON=py -3.12"
  ) else (
    echo Necesitas Python 3.12 o 3.13 de 64 bits.
    pause
    exit /b 1
  )
)
%PYTHON% -m venv ".venv"
if errorlevel 1 goto error
".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto error
".venv\Scripts\python.exe" -m pip install -r "requirements_bloqueadas.txt"
if errorlevel 1 goto error
".venv\Scripts\python.exe" -c "import cadquery,numpy,scipy,trimesh,vtk,shapely,uvicorn,fastapi,manifold3d,psutil,networkx; print('Entorno CAD experimental preparado')"
if errorlevel 1 goto error
echo.
echo Instalacion terminada. Ejecuta Iniciar.bat.
pause
exit /b 0
:error
echo ERROR instalando dependencias. Verifica la conexion y vuelve a ejecutar este instalador.
pause
exit /b 1
