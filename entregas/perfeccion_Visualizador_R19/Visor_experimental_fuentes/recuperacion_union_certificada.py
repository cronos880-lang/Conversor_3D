"""Recuperar una unión booleana verificada cuando su ajuste CAD no es exacto.

Regenera la unión desde el original, exige los mismos bytes preparados y
aplica la recuperación conservadora existente sobre esa frontera exterior.
Una abertura o un archivo preparado arbitrario nunca autorizan esta ruta.
"""
from pathlib import Path
import hashlib,tempfile

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def ejecutar(source,prepared,destination,log):
    from preprocesador_stl import preparar,cargar_exacto
    from recuperacion_numerica import ejecutar_aislado
    source,prepared,destination=map(Path,[source,prepared,destination])
    if (destination.resolve() in [source.resolve(),prepared.resolve()]
            or any(destination.exists() and destination.samefile(p) for p in [source,prepared])):
        raise ValueError('La salida debe ser distinta del original y su unión.')
    hashes=[sha(source),sha(prepared)]
    with tempfile.TemporaryDirectory(prefix='visor_union_certificada_') as directory:
        reference,proof=preparar(source,Path(directory)/'union.stl')
        if (proof.get('reparado') is not True
                or proof.get('ruta_seleccionada')!='union_booleana_verificada'
                or proof.get('original_sha256')!=hashes[0]
                or proof.get('reparado_sha256')!=hashes[1]
                or sha(reference)!=hashes[1]):
            raise ValueError('La entrada preparada no coincide con la unión regenerada desde el original.')
        candidate=Path(directory)/'candidato.step'
        # La referencia es la frontera EXTERIOR de la unión. Los contactos
        # interiores ya se contrastaron con otro booleano independiente OCC.
        result=ejecutar_aislado(reference,reference,candidate,log)
        from calidad_topologica import leer_solido_step_estricto
        from saneamiento_cad import exigir_coherencia_exacta
        exigir_coherencia_exacta(leer_solido_step_estricto(candidate))
        if hashes!=[sha(source),sha(prepared)]:
            raise ValueError('La entrada cambió después de verificar su unión.')
        result['caras_stl']=int(len(cargar_exacto(source).faces))
        result['calidad']['union_original_verificada']={
            'original_sha256':hashes[0],'preparado_sha256':hashes[1],
            'referencia':'Frontera exterior de la unión regenerada desde los componentes originales',
            'verificacion_independiente':proof['verificacion_independiente'],
            'verificacion_stl_reimportado':proof['verificacion_stl_reimportado'],
            'limites_modificados':False}
        result['estrategia']='union_booleana_recuperacion_facetada_verificada'
        destination.write_bytes(candidate.read_bytes())
        return result
