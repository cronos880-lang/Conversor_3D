"""Contratos e integridad de archivos del pipeline B-Rep R19."""
from pathlib import Path
import hashlib
import json
import os
import sys

ROOT = Path(__file__).resolve().parent
for folder in (ROOT / 'motor_superficies', ROOT / 'motor_calidad'):
    if str(folder) not in sys.path:
        sys.path.append(str(folder))
TOLERANCIA_COSTURA_MM = 1e-7
TOLERANCIA_PCURVA_MM = 5e-8
MAX_CARAS_CAD = 1200
MAX_TRIANGULOS_OPTIMIZACION = 50000


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def escribir_json(path, value):
    """Informe atómico; sólo se reemplaza un informe del trabajo actual."""
    path = Path(path)
    temporary = path.with_name(path.name + '.tmp')
    with temporary.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
    os.replace(temporary, path)


def copiar_nuevo(source, destination):
    source, destination = map(Path, (source, destination))
    expected = sha(source)
    with source.open('rb') as src, destination.open('xb') as dst:
        import shutil
        shutil.copyfileobj(src, dst)
    if sha(destination) != expected or sha(source) != expected:
        raise ValueError('La copia no conserva sus bytes')
    return expected


def ultimo_json(path):
    for line in reversed(Path(path).read_text(encoding='utf-8', errors='replace').splitlines()):
        try:
            value = json.loads(line)
        except ValueError:
            continue
        if isinstance(value, dict) and 'ok' in value:
            return value
    raise ValueError('El proceso no emitió un resultado JSON completo')


def rutas_nuevas(source, destination):
    source, destination = map(lambda p: Path(p).resolve(), (source, destination))
    evidence = destination.with_suffix('.r19')
    reserved = [destination, evidence, destination.with_suffix('.r19_pipeline.json'),
                destination.with_suffix('.r19_nucleo.json'), destination.with_suffix('.motor.log'),
                destination.with_name(destination.name + '.r19_base_validada.step'),
                destination.with_name(destination.name + '.r19_base_validada.json'),
                destination.with_name(destination.name + '.r19_seleccion.tmp')]
    if not source.is_file() or source == destination or any(p.exists() for p in reserved):
        raise ValueError('Entrada existente y salidas nuevas y distintas son obligatorias')
    if not destination.parent.is_dir():
        raise ValueError('El directorio de salida debe existir')
    return source, destination, evidence
