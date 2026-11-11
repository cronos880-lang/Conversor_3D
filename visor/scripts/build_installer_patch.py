"""Crear una reparación de fuentes R20 que conserva el entorno y los datos existentes."""
from pathlib import Path, PurePosixPath
import argparse
import hashlib
import json
import zipfile

from build_r20 import PREFIX


def read_archive(path):
    with zipfile.ZipFile(path) as archive:
        manifest = json.loads(archive.read(PREFIX + '/R20_MANIFEST.json'))
        files = {}
        for name, digest in manifest['files'].items():
            relative = PurePosixPath(name)
            if relative.is_absolute() or '..' in relative.parts or '\\' in name or ':' in name:
                raise ValueError('Ruta no válida en el manifiesto')
            data = archive.read(PREFIX + '/' + name)
            if hashlib.sha256(data).hexdigest() != digest:
                raise ValueError('Hash incorrecto: ' + name)
            files[name] = data
        files['R20_MANIFEST.json'] = archive.read(PREFIX + '/R20_MANIFEST.json')
        return manifest, files


def build(old_archive, new_archive, output):
    old, before = read_archive(old_archive)
    new, after = read_archive(new_archive)
    if old['identity']['release'] != 'R20' or new['identity']['release'] != 'R20':
        raise ValueError('La reparación sólo admite R20')
    if set(before) - set(after):
        raise ValueError('Una reparación por superposición no puede borrar archivos')
    changed = {name: data for name, data in after.items() if before.get(name) != data}
    if any(name.startswith(('datos/', '.venv_r20/', 'visor/src/conversor3d/', 'entregas/'))
           for name in changed):
        raise ValueError('La reparación del instalador no modifica datos, entorno ni motor')
    changed['LEEME_REPARACION_R20.txt'] = (
        'REPARACION DEL INSTALADOR R20\n\n'
        '1. Cierra la ventana del instalador anterior.\n'
        '2. Extrae TODO este ZIP DENTRO de tu carpeta Conversor_3D_R20_experimental.\n'
        '   Acepta sustituir los archivos. Este paquete no contiene .venv_r20 ni datos.\n'
        '3. Abre Reparar_Entorno_R20.bat. Retoma los paquetes que falten y verifica los existentes.\n'
        '4. Al terminar, abre Iniciar_R20.bat.\n\n'
        'Veras PAQUETE N/TOTAL y mensajes EN CURSO durante operaciones largas.\n'
        'Registro: datos/instalacion_R20.log. No hay cambios del motor geometrico.\n'
    ).encode('utf-8')
    record = {'schema': 1, 'installer_revision': new['identity']['installer_revision'],
              'base_zip_sha256': hashlib.sha256(Path(old_archive).read_bytes()).hexdigest(),
              'corrected_zip_sha256': hashlib.sha256(Path(new_archive).read_bytes()).hexdigest(),
              'source_commit': new['source_commit'], 'preserves_existing_environment_and_data': True,
              'files': {name: hashlib.sha256(data).hexdigest() for name, data in sorted(changed.items())}}
    changed['R20_REPARACION.json'] = json.dumps(record, indent=2).encode('utf-8')
    with zipfile.ZipFile(output, 'x') as archive:
        for name, data in sorted(changed.items()):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.create_system = 0
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, data, compresslevel=9)
    report = {'zip': str(output), 'files': len(changed), 'bytes': Path(output).stat().st_size,
              'sha256': hashlib.sha256(Path(output).read_bytes()).hexdigest()}
    print(json.dumps(report), flush=True)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--old-archive', type=Path, required=True)
    parser.add_argument('--new-archive', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    build(args.old_archive, args.new_archive, args.output)
