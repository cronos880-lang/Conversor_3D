@echo off
setlocal
if not exist "%~dp0entregas\perfeccion_Visualizador_R17\Iniciar.bat" (
  where py >nul 2>&1
  if errorlevel 1 (
    python "%~dp0entregas\perfeccion_Visualizador_R17\ensamblar_entrega.py"
  ) else (
    py -3.12 "%~dp0entregas\perfeccion_Visualizador_R17\ensamblar_entrega.py"
  )
  if errorlevel 1 (
    echo No se ha podido verificar la entrega. Revisa Python 3.12.
    pause
    exit /b 1
  )
)
call "%~dp0entregas\perfeccion_Visualizador_R17\Iniciar.bat"
