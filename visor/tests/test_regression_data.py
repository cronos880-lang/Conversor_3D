"""La limpieza de versiones conserva exactamente los datos de pruebas requeridos."""
from pathlib import Path
import hashlib
import json
import zipfile


def test_six_historical_fixture_files_keep_their_original_hashes():
    root = Path(__file__).resolve().parents[1] / 'test-data'
    manifest = json.loads((root / 'r5_regression.json').read_text(encoding='utf-8'))
    archive = root / manifest['archive']
    assert hashlib.sha256(archive.read_bytes()).hexdigest() == manifest['archive_sha256']
    with zipfile.ZipFile(archive) as bundle:
        assert len(bundle.namelist()) == 6
        assert set(bundle.namelist()) == set(manifest['files'])
        for name, expected in manifest['files'].items():
            data = bundle.read(name)
            assert len(data) == expected['bytes']
            assert hashlib.sha256(data).hexdigest() == expected['sha256']
