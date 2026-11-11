import pytest
from conversor3d.settings import Settings
from conversor3d._version import __version__, DEFAULT_PORT


def test_settings_have_one_identity_and_explicit_units(tmp_path):
    settings = Settings.read({'CONVERSOR3D_PROJECT_ROOT': str(tmp_path), 'CONVERSOR3D_PORT': '9000'})
    assert settings.port == 9000
    assert settings.cache_dir == tmp_path / 'visor/data/cache'
    assert settings.describe()['version'] == __version__
    assert settings.describe()['fixed_cad_tolerance_mm'] == 1e-7
    assert settings.identity(9000) != settings.identity(9001)
    assert Settings.read({}).port == DEFAULT_PORT


@pytest.mark.parametrize('values', [
    {'CONVERSOR3D_PORT': 'abc'}, {'CONVERSOR3D_PORT': '1'},
    {'CONVERSOR3D_RETENTION_DAYS': '-1'}, {'VISOR_PERFIL': 'unsafe'},
    {'CONVERSOR3D_CACHE_ENABLED': 'maybe'}, {'CONVERSOR3D_DATA_DIR': ''},
])
def test_invalid_settings_fail_before_native_work(values):
    with pytest.raises(ValueError):
        Settings.read(values)
