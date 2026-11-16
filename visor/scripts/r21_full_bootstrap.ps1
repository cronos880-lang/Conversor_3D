# Windows PowerShell 5.1. No busca ni modifica instalaciones R20.
$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$forwarded = @($args)
function Find-BasePython([string]$command, [string[]]$prefixArgs) {
    try {
        $code = "import sys,struct;from pathlib import Path;assert sys.version_info[:2]==(3,12) and struct.calcsize('P')==8;print(Path(sys.base_prefix)/'python.exe')"
        $answer = @(& $command @prefixArgs -I -c $code 2>$null)
        if ($LASTEXITCODE -eq 0 -and $answer.Count -gt 0 -and (Test-Path -LiteralPath $answer[-1] -PathType Leaf)) {
            return [string]$answer[-1]
        }
    } catch { }
    return $null
}
try {
    $python = Join-Path $root '.venv_r21\Scripts\python.exe'
    if ($forwarded.Count -gt 0 -and $forwarded[0] -eq 'install' -and (Test-Path -LiteralPath $python)) {
        $python = Find-BasePython $python @()
    }
    if (!$python -or !(Test-Path -LiteralPath $python -PathType Leaf)) {
        $python = $null
        $py = Get-Command py.exe -ErrorAction SilentlyContinue
        if ($py) { $python = Find-BasePython $py.Source @('-3.12') }
        if (!$python) {
            $command = Get-Command python.exe -ErrorAction SilentlyContinue
            if ($command -and $command.Source -notlike '*\WindowsApps\*') {
                $python = Find-BasePython $command.Source @()
            }
        }
        if (!$python) {
            foreach ($key in @('HKCU:\Software\Python\PythonCore\3.12\InstallPath',
                               'HKLM:\Software\Python\PythonCore\3.12\InstallPath')) {
                if (Test-Path $key) {
                    $folder = (Get-Item $key).GetValue('')
                    if ($folder) {
                        $candidate = Join-Path $folder 'python.exe'
                        if (Test-Path -LiteralPath $candidate) { $python = Find-BasePython $candidate @() }
                    }
                }
                if ($python) { break }
            }
        }
        if (!$python) { throw 'Se necesita Python 3.12 x64. Instalar desde https://www.python.org/downloads/windows/ y volver a abrir Iniciar_R21.bat.' }
    }
    & $python -B (Join-Path $root 'visor\scripts\manage_environment_r21.py') @forwarded
    exit $LASTEXITCODE
} catch {
    Write-Host ('ERROR R21 COMPLETA: ' + $_.Exception.Message)
    exit 2
}
