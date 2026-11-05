"""El rechazo y los temporales tampoco pueden modificar la entrada original."""
import pytest
from reparador_exacto_aislado import ejecutar


@pytest.mark.parametrize('conflict',['salida','informe','temporal','control'])
def test_original_intacto_si_las_rutas_colisionan(tmp_path,conflict):
    source=tmp_path/'original.stl'
    destination=tmp_path/'regularizado.stl'
    report=tmp_path/'informe.json'
    if conflict=='salida':destination=source
    elif conflict=='informe':report=source
    elif conflict=='temporal':source=destination.with_suffix('.pendiente.stl')
    else:source=destination.with_suffix('.control.off')
    contents=b'original que no se puede borrar ni sobrescribir'
    source.write_bytes(contents)
    assert ejecutar(source,destination,report)==2
    assert source.read_bytes()==contents
