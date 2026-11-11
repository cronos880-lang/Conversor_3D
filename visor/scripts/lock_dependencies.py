"""Fijar artefactos de PyPI compatibles con los entornos x64 ya comprobados."""
from pathlib import Path
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import urllib.request
from packaging.markers import default_environment
from packaging.requirements import Requirement
from packaging.tags import cpython_tags, compatible_tags
from packaging.utils import canonicalize_name, parse_wheel_filename


def metadata(name, version):
    url = f'https://pypi.org/pypi/{name}/{version}/json'
    with urllib.request.urlopen(url, timeout=30) as response:
        return json.load(response)


def build(target, versions, output):
    versions = {canonicalize_name(name): version for name, version in versions.items()}
    if target == 'windows':
        platforms = ['win_amd64']
        env = {'sys_platform': 'win32', 'os_name': 'nt', 'platform_system': 'Windows'}
    else:
        platforms = [f'manylinux_2_{n}_x86_64' for n in range(5, 40)]
        platforms += ['manylinux1_x86_64', 'manylinux2010_x86_64', 'manylinux2014_x86_64', 'linux_x86_64']
        env = {'sys_platform': 'linux', 'os_name': 'posix', 'platform_system': 'Linux'}
    env = {**default_environment(), **env, 'python_version': '3.12',
           'python_full_version': '3.12.10', 'platform_machine': 'AMD64' if target == 'windows' else 'x86_64', 'extra': ''}
    tags = set(cpython_tags((3, 12), abis=['cp312'], platforms=platforms))
    tags.update(compatible_tags((3, 12), interpreter='cp312', platforms=platforms))
    names = sorted(versions)
    with ThreadPoolExecutor(max_workers=8) as pool:
        values = list(pool.map(lambda name: metadata(name, versions[name]), names))
    data = dict(zip(names, values))
    # La lista debe cerrar todas las dependencias activas, sin URLs ni omisiones.
    for name, document in data.items():
        for text in document['info'].get('requires_dist') or []:
            requirement = Requirement(text)
            if requirement.marker and not requirement.marker.evaluate(env):
                continue
            dependency = canonicalize_name(requirement.name)
            if requirement.url or dependency not in versions or versions[dependency] not in requirement.specifier:
                raise ValueError(f'Lista no cerrada para {target}: {name} requiere {text}')
    lines = [f'# CPython 3.12 x64 / {target}. Artefactos PyPI con SHA-256.',
             '# Generado desde versiones resueltas y comprobadas; no usar sdists sin revisar.', '']
    manifest = []
    for name in names:
        files = []
        for record in data[name]['urls']:
            if record['packagetype'] != 'bdist_wheel':
                continue
            _, _, _, wheel_tags = parse_wheel_filename(record['filename'])
            if tags.intersection(wheel_tags):
                files.append(record)
        hashes = sorted({record['digests']['sha256'] for record in files})
        if not hashes:
            raise ValueError('No hay wheel compatible para ' + name)
        lines.append(f'{name}=={versions[name]} \\')
        for i, digest in enumerate(hashes):
            lines.append('    --hash=sha256:' + digest + (' \\' if i != len(hashes) - 1 else ''))
        lines.append('')
        manifest.append({'name': name, 'version': versions[name], 'pypi': f'https://pypi.org/project/{name}/{versions[name]}/',
                         'wheels': [record['filename'] for record in files]})
    output.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    output.with_suffix('.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print(target, len(names), 'paquetes fijados', flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--linux-report', type=Path, required=True)
    p.add_argument('--windows-inventory', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    linux = {r['metadata']['name']: r['metadata']['version'] for r in json.loads(args.linux_report.read_text())['install']}
    windows = {r['name']: r['version'] for r in json.loads(args.windows_inventory.read_text())}
    windows['python-multipart'] = '0.0.31'
    windows.update({'pytest': '9.0.2', 'httpx': '0.28.1', 'httpcore': '1.0.9',
                    'iniconfig': '2.3.1', 'pluggy': '1.7.0', 'pygments': '2.21.0',
                    'certifi': '2026.10.23', 'colorama': '0.4.6'})
    build('linux', linux, args.output / 'requirements-linux-py312.lock')
    build('windows', windows, args.output / 'requirements-windows-py312.lock')
