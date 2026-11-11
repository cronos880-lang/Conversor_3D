"""Perfilado optativo de procesos Python sin modificar el motor congelado."""
import os

_folder = os.environ.get('CONVERSOR3D_PROFILE_DIR')
if _folder:
    import atexit
    import cProfile
    from pathlib import Path
    import uuid
    _path = Path(_folder)
    _path.mkdir(parents=True, exist_ok=True)
    _target = _path / (str(os.getpid()) + '-' + uuid.uuid4().hex + '.prof')
    _profile = cProfile.Profile()
    _profile.enable()

    def _save_profile():
        _profile.disable()
        _profile.dump_stats(str(_target))

    atexit.register(_save_profile)
