"""Proceso proponente sin acceso a la autoridad de aprobación."""
from pathlib import Path
import json
import sys
import traceback
from .geometry import propose


def main():
    path = Path(sys.argv[1])
    job = json.loads(path.read_text(encoding='utf-8'))
    try:
        result = {'ok': True, 'proposal': propose(Path(job['baseline']), Path(job['candidate']))}
    except Exception as error:
        traceback.print_exc()
        result = {'ok': False, 'error': str(error), 'accepted': False,
                  'error_code': getattr(error, 'code', type(error).__name__)}
    (path.parent / 'proposal.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    return 0 if result['ok'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
