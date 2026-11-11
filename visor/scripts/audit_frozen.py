"""Auditoría sin importar ni modificar las copias deliberadamente congeladas."""
from pathlib import Path
import argparse
import collections
import hashlib
import json

REPO = Path(__file__).resolve().parents[2]
DEFAULT_ROOT = REPO / 'entregas/perfeccion_Visualizador_R19/Visor_experimental_fuentes'
DEFAULT_MANIFEST = REPO / 'visor/frozen-r19.sha256.json'


def audit(root: Path, manifest: Path):
    expected = json.loads(Path(manifest).read_text(encoding='utf-8'))
    errors, names, contents = [], collections.defaultdict(list), collections.defaultdict(list)
    for name, digest in expected.items():
        path = Path(root) / name
        if not path.is_file():
            errors.append({'file': name, 'reason': 'missing'})
            continue
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != digest:
            errors.append({'file': name, 'reason': 'hash_changed'})
        if path.suffix == '.py':
            names[path.name].append({'path': name, 'sha256': actual})
            contents[actual].append(name)
    return {'verified_files': len(expected), 'errors': errors,
            'divergent_module_names': {name: rows for name, rows in names.items()
                                       if len({r['sha256'] for r in rows}) > 1},
            'identical_copies': {digest: paths for digest, paths in contents.items() if len(paths) > 1},
            'policy': 'No se unifican implementaciones divergentes ni copias de validación congeladas'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=DEFAULT_ROOT)
    parser.add_argument('--manifest', type=Path, default=DEFAULT_MANIFEST)
    args = parser.parse_args()
    result = audit(args.root, args.manifest)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(2 if result['errors'] else 0)
