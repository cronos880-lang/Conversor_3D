from pathlib import Path
import hashlib
import importlib.util
import json
from conversor3d.legacy import REPO


def auditor():
    path = REPO / 'visor/scripts/audit_frozen.py'
    spec = importlib.util.spec_from_file_location('frozen_audit_script', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_all_357_historical_files_remain_identical():
    module = auditor()
    report = module.audit(module.DEFAULT_ROOT, module.DEFAULT_MANIFEST)
    assert report['verified_files'] == 357 and not report['errors']
    assert len(report['divergent_module_names']) == 32


def test_audit_detects_modified_source_without_importing_it(tmp_path):
    source = tmp_path / 'module.py'
    source.write_bytes(b'raise RuntimeError("must not execute")\n')
    manifest = tmp_path / 'manifest.json'
    manifest.write_text(json.dumps({'module.py': hashlib.sha256(source.read_bytes()).hexdigest()}))
    module = auditor()
    assert not module.audit(tmp_path, manifest)['errors']
    source.write_bytes(b'changed\n')
    assert module.audit(tmp_path, manifest)['errors'][0]['reason'] == 'hash_changed'
