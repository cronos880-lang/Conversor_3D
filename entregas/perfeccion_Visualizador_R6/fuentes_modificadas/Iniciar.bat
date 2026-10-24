@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
 echo No se ha preparado el entorno aislado del conversor.
 echo Ejecuta primero Instalar_Entorno.bat una sola vez.
 pause
 exit /b 1
)
".venv\Scripts\python.exe" -c "import gpytoolbox_bindings_copyleft,CGAL,igl,cadquery,trimesh,scipy,numpy,shapely,vtk,fastapi,uvicorn,multipart,manifold3d,psutil,networkx" >nul 2>&1
if errorlevel 1 (
 echo Dependencias incompletas. Ejecuta Instalar_Entorno.bat.
 pause
 exit /b 1
)
set "PYTHONIOENCODING=utf-8"
echo Copia EXPERIMENTAL. Consultar ESTADO_VALIDACION.md antes de usar los resultados.
start "" "http://127.0.0.1:8770"
".venv\Scripts\python.exe" servidor.py
if errorlevel 1 pause
