import json
from pathlib import Path
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from conversor3d.security import LocalAccessMiddleware
from conversor3d.retention import cleanup_records


@pytest.mark.parametrize('headers,status', [
    ({'Host': 'evil.example:9000'}, 400),
    ({'Origin': 'https://evil.example'}, 403),
    ({'Origin': 'null'}, 403),
    ({'Sec-Fetch-Site': 'cross-site'}, 403),
    ({'Origin': 'http://127.0.0.1:9000'}, 200),
    ({}, 200),
])
def test_foreign_requests_never_enter_conversion(headers, status):
    app = FastAPI()
    entered = []
    @app.post('/convertir')
    def convert():
        entered.append(True)
        return {'ok': True}
    app.add_middleware(LocalAccessMiddleware, port=9000)
    with TestClient(app, base_url='http://127.0.0.1:9000') as client:
        response = client.post('/convertir', content=b'unparsed body', headers=headers)
    assert response.status_code == status
    assert bool(entered) == (status == 200)


def job(folder, name, completed=0, owned=True):
    (folder / (name + '.json')).write_text(json.dumps({
        'conversor3d_owned': owned, 'conversor3d_completed_at': completed}))
    (folder / (name + '.step')).write_bytes(b'user result')


def test_retention_preserves_default_active_and_foreign_data(tmp_path):
    old, active, foreign, recent = ('a'*12, 'b'*12, 'c'*12, 'd'*12)
    job(tmp_path, old); job(tmp_path, active); job(tmp_path, foreign, owned=False)
    job(tmp_path, recent, completed=200000)
    assert cleanup_records(tmp_path, 0, now=200001)['removed_jobs'] == []
    cleaned = cleanup_records(tmp_path, 1, [active], now=200001)
    assert cleaned['removed_jobs'] == [old]
    assert all((tmp_path / (name + '.step')).exists() for name in [active, foreign, recent])


def test_retention_never_follows_links(tmp_path):
    records = tmp_path / 'records'; records.mkdir()
    name = 'e'*12; job(records, name)
    secret = tmp_path / 'outside.stl'; secret.write_bytes(b'original model')
    try:
        (records / (name + '.external')).symlink_to(secret)
    except OSError:
        pytest.skip('El sistema no permite crear enlaces simbólicos de prueba')
    cleaned = cleanup_records(records, 1, now=200001)
    assert not cleaned['removed_jobs'] and cleaned['skipped']
    assert secret.read_bytes() == b'original model'
    assert (records / (name + '.step')).exists()


def test_updated_form_parser_preserves_semicolon_as_data():
    from fastapi import Request
    app = FastAPI()
    @app.post('/form')
    async def form(request: Request):
        return dict(await request.form())
    with TestClient(app) as client:
        response = client.post('/form', content='a=1;b=2',
                               headers={'Content-Type': 'application/x-www-form-urlencoded'})
    assert response.json() == {'a': '1;b=2'}


def test_incomplete_diagnostic_is_preserved(tmp_path):
    name = 'f'*12
    job(tmp_path, name)
    (tmp_path / (name + '.json')).write_text('[]')
    cleaned = cleanup_records(tmp_path, 1, now=200001)
    assert not cleaned['removed_jobs'] and (tmp_path / (name + '.step')).exists()
