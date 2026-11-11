"""Limpiar sólo grupos terminales propios, con conservación por defecto."""
from pathlib import Path
import json
import math
import re
import time


def cleanup_records(folder: Path, days: int, active_ids=(), now=None):
    if days < 0:
        raise ValueError('Los días de conservación no pueden ser negativos')
    result = {'removed_jobs': [], 'removed_files': [], 'skipped': []}
    if days == 0:
        return result
    root = Path(folder).resolve()
    if not root.exists():
        return result
    cutoff = (time.time() if now is None else now) - days * 86400
    active = set(active_ids)
    for metadata in root.glob('*.json'):
        job = metadata.stem
        if not re.fullmatch(r'[0-9a-f]{12}', job) or job in active or metadata.is_symlink():
            continue
        try:
            record = json.loads(metadata.read_text(encoding='utf-8'))
            if not isinstance(record, dict):
                result['skipped'].append({'job': job, 'reason': 'Diagnóstico incompleto'})
                continue
            finished = record.get('conversor3d_completed_at')
            if record.get('conversor3d_owned') is not True:
                continue
            if (not isinstance(finished, (int, float)) or isinstance(finished, bool)
                    or not math.isfinite(finished) or finished > cutoff):
                continue
            members = [path for path in root.iterdir() if path.name.startswith(job + '.')]
            if any(path.is_symlink() or not path.is_file() or path.resolve().parent != root for path in members):
                result['skipped'].append({'job': job, 'reason': 'Enlace o directorio fuera del formato propio'})
                continue
            # El diagnóstico se elimina al final: un fallo parcial permite reintentar.
            for path in sorted(members, key=lambda p: p == metadata):
                path.unlink()
                result['removed_files'].append(path.name)
            result['removed_jobs'].append(job)
        except (OSError, ValueError, TypeError) as error:
            result['skipped'].append({'job': job, 'reason': str(error)})
    return result
