"""Resume perfiles propios de cProfile; no suma tiempos acumulados solapados."""
from pathlib import Path
import argparse
import json
import pstats

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('folder', type=Path)
args = p.parse_args()
rows = []
for path in sorted(args.folder.glob('*.prof')):
    stats = pstats.Stats(str(path))
    functions = []
    for (filename, line, name), (primitive, calls, internal, cumulative, _) in stats.stats.items():
        if 'Conversor_3D' in filename or 'conversor3d' in filename:
            functions.append({'file': filename, 'line': line, 'function': name,
                              'calls': calls, 'internal_seconds': internal,
                              'cumulative_seconds': cumulative})
    rows.append({'profile': path.name, 'total_seconds': stats.total_tt,
                 'top_functions': sorted(functions, key=lambda r: -r['cumulative_seconds'])[:25]})
print(json.dumps(rows, ensure_ascii=False, indent=2))
