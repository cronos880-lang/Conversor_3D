"""La auditoría conserva avisos mixtos y no infiere permisos desde un clasificador."""
from email.message import Message
import importlib.util
from pathlib import Path
import sys

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
spec = importlib.util.spec_from_file_location('visor_license_audit', SCRIPTS / 'audit_licenses.py')
audit_module = importlib.util.module_from_spec(spec)
sys.path.insert(0, str(SCRIPTS))
try:
    spec.loader.exec_module(audit_module)
finally:
    sys.path.remove(str(SCRIPTS))


def test_preserves_mixed_notices_despite_mit_metadata(tmp_path):
    metadata = Message()
    metadata['License'] = 'MIT'
    metadata['Classifier'] = 'License :: OSI Approved :: MIT License'
    paths = ['example.dist-info/licenses/LICENSE.MIT', 'example.dist-info/licenses/LICENSE.GPL']
    ignored = ['example/licenses/__init__.py',
               'example/licenses/__pycache__/__init__.cpython-312.pyc']
    for relative in paths + ignored:
        file = tmp_path / relative
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(relative, encoding='utf-8')

    class Distribution:
        version = '1.0'
        files = paths + ignored

        def locate_file(self, file):
            return tmp_path / file

    dist = Distribution()
    dist.metadata = metadata
    result = audit_module.distribution_record('example', dist)
    assert {item['path'] for item in result['notice_files']} == set(paths)
    assert all(len(item['sha256']) == 64 for item in result['notice_files'])
    assert result['license_metadata_first_line'] == 'MIT'
    assert result['license_expression'] == ''


def test_runtime_audit_does_not_include_test_dependencies_or_grant_permission():
    report = audit_module.audit()
    names = {item['name'] for item in report['distributions']}
    assert {'cadquery-ocp', 'cgal', 'vtk', 'gpytoolbox'} <= names
    assert 'pytest' not in names
    assert report['redistribution_approved'] is False
    cgal = next(item for item in report['distributions'] if item['name'] == 'cgal')
    assert any(item['path'].endswith('LICENSE.GPL') for item in cgal['notice_files'])
