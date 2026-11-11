"""Configuración validada con unidades; las tolerancias CAD no son configurables."""
from dataclasses import dataclass
from pathlib import Path
import hashlib
import os
from ._version import APPLICATION_LABEL, BASE_ENGINE, DEFAULT_PORT, __version__


@dataclass(frozen=True)
class Settings:
    project_root: Path
    frozen_root: Path
    data_dir: Path
    cache_dir: Path
    port: int
    profile: str
    cache_enabled: bool
    retention_days: int
    profiling_dir: Path | None = None

    @classmethod
    def read(cls, env=None):
        values = os.environ if env is None else env
        for key in ('CONVERSOR3D_PROJECT_ROOT', 'CONVERSOR3D_FROZEN_ROOT',
                    'CONVERSOR3D_DATA_DIR', 'CONVERSOR3D_CACHE_DIR'):
            if key in values and not values[key].strip():
                raise ValueError(key + ' no puede ser una ruta vacía')
        project = Path(values.get('CONVERSOR3D_PROJECT_ROOT', str(Path(__file__).resolve().parents[3]))).resolve()
        frozen = Path(values.get('CONVERSOR3D_FROZEN_ROOT',
            str(project / f'entregas/perfeccion_Visualizador_{BASE_ENGINE}/Visor_experimental_fuentes'))).resolve()
        data = Path(values.get('CONVERSOR3D_DATA_DIR', str(project / 'visor/data'))).resolve()
        cache = Path(values.get('CONVERSOR3D_CACHE_DIR', str(data / 'cache'))).resolve()
        try:
            port = int(values.get('CONVERSOR3D_PORT', values.get('VISOR_PORT', str(DEFAULT_PORT))))
            retention = int(values.get('CONVERSOR3D_RETENTION_DAYS', '0'))
        except ValueError as error:
            raise ValueError('Puerto y días de conservación deben ser números enteros') from error
        if not 1024 <= port <= 65535 or retention < 0:
            raise ValueError('Puerto fuera de 1024–65535 o conservación negativa')
        profile = values.get('VISOR_PERFIL', 'precision')
        if profile not in ('precision', 'impresion'):
            raise ValueError('VISOR_PERFIL debe ser precision o impresion')
        enabled = values.get('CONVERSOR3D_CACHE_ENABLED', '1').lower()
        if enabled not in ('0', '1', 'true', 'false'):
            raise ValueError('CONVERSOR3D_CACHE_ENABLED debe ser 0, 1, true o false')
        for name, path in [('datos', data), ('caché', cache)]:
            if path.exists() and not path.is_dir():
                raise ValueError(f'La ruta de {name} debe ser un directorio')
        profiling = values.get('CONVERSOR3D_PROFILE_DIR')
        return cls(project, frozen, data, cache, port, profile,
                   enabled in ('1', 'true'), retention, Path(profiling).resolve() if profiling else None)

    def environment(self):
        result = {'CONVERSOR3D_PROJECT_ROOT': str(self.project_root),
                  'CONVERSOR3D_FROZEN_ROOT': str(self.frozen_root),
                  'CONVERSOR3D_DATA_DIR': str(self.data_dir), 'CONVERSOR3D_CACHE_DIR': str(self.cache_dir),
                  'CONVERSOR3D_PORT': str(self.port), 'VISOR_PERFIL': self.profile,
                  'CONVERSOR3D_CACHE_ENABLED': str(int(self.cache_enabled)),
                  'CONVERSOR3D_RETENTION_DAYS': str(self.retention_days)}
        if self.profiling_dir:
            result['CONVERSOR3D_PROFILE_DIR'] = str(self.profiling_dir)
        return result

    def identity(self, port=None):
        instance = f'{self.project_root}|{self.data_dir}|{port or self.port}'
        return {'version': APPLICATION_LABEL, 'compilacion': __version__,
                'instancia': hashlib.sha256(instance.encode()).hexdigest()[:20]}

    def describe(self):
        units = {'CONVERSOR3D_PORT': 'puerto TCP', 'VISOR_PERFIL': 'perfil',
                 'CONVERSOR3D_RETENTION_DAYS': 'días; 0 conserva',
                 'CONVERSOR3D_CACHE_ENABLED': 'booleano'}
        return {'version': __version__, 'base_engine': BASE_ENGINE,
                'settings': {key: {'value': value, 'unit': units.get(key, 'ruta de directorio')}
                             for key, value in self.environment().items()},
                'fixed_cad_tolerance_mm': 1e-7}
