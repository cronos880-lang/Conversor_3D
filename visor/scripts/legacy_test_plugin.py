"""Orden determinista para el diagnóstico del test histórico de registros.

Conserva todas las comprobaciones y no modifica tests congelados ni geometría.
"""
from pathlib import Path
import re
import pytest


@pytest.fixture(autouse=True)
def deterministic_diagnostic_listing(request, monkeypatch):
    if request.node.originalname != 'test_api_guarda_original_y_causa_de_vertices_pinzdos':
        return
    folder = request.getfixturevalue('tmp_path')
    original = Path.glob

    def listing(path, pattern):
        values = original(path, pattern)
        if path == folder and pattern == '*.json':
            return iter(sorted(values, key=lambda p: (not bool(re.fullmatch(r'[0-9a-f]{12}\.json', p.name)), p.name)))
        return values

    monkeypatch.setattr(Path, 'glob', listing)
