"""Contratos visuales sin ejecutar ni alterar el motor CAD."""
from pathlib import Path
import shutil
import subprocess

import pytest

from conversor3d._version import APPLICATION_LABEL
from conversor3d.server import viewer_html, VIEWER


def test_development_viewer_has_resolved_identity_and_local_assets():
    html = viewer_html()
    assert f'<title>{APPLICATION_LABEL}</title>' in html
    assert '__APPLICATION_LABEL__' not in html
    assert '/viewer/presentation.js' in html
    assert (VIEWER / 'presentation.js').is_file()


def test_progress_lifecycle_and_display_geometry():
    node = shutil.which('node')
    if not node:
        pytest.skip('Node no disponible para comprobar los helpers de presentación JavaScript')
    subprocess.run([node, '--test', str(Path(__file__).with_name('viewer_presentation.test.cjs'))],
                   check=True, capture_output=True, text=True)
