"""Inventariar procedencia y avisos del runtime sin asignar una licencia al proyecto."""
from pathlib import Path
import argparse
import hashlib
import json
import platform
import re
import sys

from build_portable import REPO, distributions

NOTICE_NAME = re.compile(
    r'^(?:licen[cs]e|copying|copyright|notice|third[-_]party[-_](?:notices|licenses))'
    r'(?:[._-].*)?$', re.IGNORECASE)


def distribution_record(name, dist):
    """Conservar todos los avisos encontrados, incluso si metadata sólo dice MIT."""
    notices = []
    for file in dist.files or []:
        relative = Path(str(file))
        # packaging/licenses es también un módulo Python. Sus fuentes y caches
        # no son avisos legales; el constructor omite deliberadamente bytecode.
        if ('__pycache__' in relative.parts
                or relative.suffix.lower() in {'.py', '.pyc', '.pyo', '.pyd', '.so', '.dll'}):
            continue
        if (not NOTICE_NAME.match(relative.name)
                and not any(part.lower() == 'licenses' for part in relative.parts[:-1])):
            continue
        path = Path(dist.locate_file(file))
        if path.is_file():
            notices.append({'path': relative.as_posix(),
                            'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
    metadata_license = dist.metadata.get('License', '')
    return {'name': name, 'version': dist.version,
            'license_expression': dist.metadata.get('License-Expression', ''),
            'license_metadata_first_line': metadata_license.splitlines()[0] if metadata_license else '',
            'license_metadata_sha256': hashlib.sha256(metadata_license.encode()).hexdigest(),
            'license_classifiers': [s for s in dist.metadata.get_all('Classifier', [])
                                    if s.startswith('License ::')],
            'project_urls': dist.metadata.get_all('Project-URL', []),
            'home_page': dist.metadata.get('Home-page', ''),
            'notice_files': sorted(notices, key=lambda item: item['path']),
            'review': 'No equivale a autorización global de redistribución'}


def audit(requirements=None):
    requirements = requirements or REPO / 'visor/requirements-runtime.txt'
    rows = [distribution_record(name, dist)
            for name, dist in sorted(distributions(requirements).items())]
    return {'schema': 1, 'python': platform.python_version(), 'platform': sys.platform,
            'scope': 'Cierre de dependencias utilizado por el constructor portable, sin paquetes de tests',
            'redistribution_approved': False,
            'missing_notice_packages': [row['name'] for row in rows if not row['notice_files']],
            'distributions': rows}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = audit()
    with args.output.open('x', encoding='utf-8') as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
    print(json.dumps({'report': str(args.output), 'distributions': len(report['distributions']),
                      'missing_notice_packages': report['missing_notice_packages'],
                      'redistribution_approved': False}, ensure_ascii=False))
