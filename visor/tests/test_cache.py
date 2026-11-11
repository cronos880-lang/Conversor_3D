import numpy as np
import trimesh
from conversor3d.cache import input_summary


def test_cache_reuses_only_identical_input_and_profile(tmp_path):
    source = tmp_path / 'source.stl'
    trimesh.creation.box().export(source)
    cache = tmp_path / 'cache'
    first = input_summary(source, cache, 'precision')
    second = input_summary(source, cache, 'precision')
    assert not first['cache_hit'] and second['cache_hit']
    assert first['summary'] == second['summary']
    assert not second['authorizes_geometry']
    assert not input_summary(source, cache, 'impresion')['cache_hit']
    trimesh.creation.box(extents=[2, 1, 1]).export(source)
    assert not input_summary(source, cache, 'precision')['cache_hit']


def test_corrupt_cache_is_recomputed_without_pickle(tmp_path):
    source = tmp_path / 'source.stl'; trimesh.creation.box().export(source)
    cache = tmp_path / 'cache'
    input_summary(source, cache, 'precision')
    next(cache.glob('*.npz')).write_bytes(b'corrupted')
    result = input_summary(source, cache, 'precision')
    assert not result['cache_hit'] and result['summary']['caras'] == 12
