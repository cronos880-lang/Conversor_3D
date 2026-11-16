# Bootstrap R21 con Windows PowerShell 5.1; no necesita py ni Python global.
$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$forwarded = @($args)
$base = $null
$explicit = $false
$noninteractive = $forwarded -contains '--no-browser'

function Test-R20([string]$path) {
    return ($path -and
        (Test-Path -LiteralPath (Join-Path $path '.venv_r20\Scripts\python.exe') -PathType Leaf) -and
        (Test-Path -LiteralPath (Join-Path $path 'entregas\perfeccion_Visualizador_R19\Visor_experimental_fuentes\motor_r19.py') -PathType Leaf))
}

try {
    for ($i = 0; $i -lt $forwarded.Count; $i++) {
        if ($forwarded[$i] -eq '--base-r20') {
            $explicit = $true
            if ($i + 1 -ge $forwarded.Count) { throw 'Falta la ruta despues de --base-r20.' }
            $base = $forwarded[$i + 1]
        }
    }
    if ($explicit -and !(Test-R20 $base)) { throw 'La carpeta indicada no contiene R20 con su entorno preparado.' }
    $candidates = New-Object 'System.Collections.Generic.List[string]'
    $saved = Join-Path $root 'datos\base_r20.json'
    if (!$base -and (Test-Path -LiteralPath $saved)) {
        try { $candidates.Add((Get-Content -LiteralPath $saved -Raw -Encoding UTF8 | ConvertFrom-Json).base_r20) } catch { }
    }
    if ($env:CONVERSOR3D_BASE_R20) { $candidates.Add($env:CONVERSOR3D_BASE_R20) }
    # Dos niveles cercanos: cubre carpetas renombradas y Extraer todo de Windows.
    $parent = Split-Path -Parent $root
    for ($level = 0; $level -lt 2 -and $parent; $level++) {
        $candidates.Add($parent)
        $children = @(Get-ChildItem -LiteralPath $parent -Directory -ErrorAction SilentlyContinue)
        foreach ($child in $children) {
            $candidates.Add($child.FullName)
            $candidates.Add((Join-Path $child.FullName 'Conversor_3D_R20_experimental'))
        }
        $parent = Split-Path -Parent $parent
    }
    if (!$base) {
        foreach ($candidate in $candidates) {
            if (Test-R20 $candidate) { $base = $candidate; break }
        }
    }
    if (!$base -and !$noninteractive) {
        Add-Type -AssemblyName System.Windows.Forms
        $dialog = New-Object System.Windows.Forms.FolderBrowserDialog
        $dialog.Description = 'Selecciona la carpeta de R20 que contiene .venv_r20'
        $dialog.ShowNewFolderButton = $false
        try {
            if ($dialog.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) { $base = $dialog.SelectedPath }
        } finally { $dialog.Dispose() }
    }
    if (!(Test-R20 $base)) { throw 'No se encontro R20 preparada. Abre R20 y ejecuta su Reparar_Entorno_R20.bat; despues selecciona esa carpeta.' }
    $base = (Resolve-Path -LiteralPath $base).Path
    Write-Host 'R21: entorno R20 localizado; comprobando archivos y bibliotecas...'
    if (!$explicit) { $forwarded = @('--base-r20', $base) + $forwarded }
    $python = Join-Path $base '.venv_r20\Scripts\python.exe'
    & $python -B (Join-Path $root 'r21_launcher.py') @forwarded
    exit $LASTEXITCODE
} catch {
    $message = 'ERROR DE ARRANQUE R21: ' + $_.Exception.Message
    Write-Host $message
    try {
        $data = Join-Path $root 'datos'
        New-Item -ItemType Directory -Path $data -Force | Out-Null
        Add-Content -LiteralPath (Join-Path $data 'arranque_R21.log') -Value $message -Encoding UTF8
    } catch { }
    exit 2
}
