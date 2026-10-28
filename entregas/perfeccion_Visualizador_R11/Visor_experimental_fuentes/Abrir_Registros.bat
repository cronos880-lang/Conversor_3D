@echo off
cd /d "%~dp0"
if not exist "Registros_Conversion" mkdir "Registros_Conversion"
start "" explorer "%cd%\Registros_Conversion"
