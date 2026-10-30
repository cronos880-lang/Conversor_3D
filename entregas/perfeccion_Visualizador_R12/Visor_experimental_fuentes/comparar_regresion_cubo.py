"""Certifica identidad de geometría STEP con la batería independiente previa.

Uso: python comparar_regresion_cubo.py --referencia CARPETA --resultados CARPETA
No vuelve a ejecutar el verificador denso; exige identidad binaria de DATA,
de los STL originales/reparados y de los indicadores históricos del CAD.
"""
import argparse,hashlib,json
from pathlib import Path


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--referencia',type=Path,required=True)
    ap.add_argument('--resultados',type=Path,required=True)
    a=ap.parse_args()
    old=json.loads((a.referencia/'bateria.json').read_text())['resultados']
    new=json.loads((a.resultados/'bateria.json').read_text())['resultados']
    checks=json.loads((a.referencia/'verificacion_independiente.json').read_text())
    assert len(old)==len(new)==len(checks)==4
    reports=[]
    for row in new:
        name=row['archivo'];previous=next(x for x in old if x['archivo']==name)
        assert row['ok'] and previous['ok'] and row['sha256']==previous['sha256']
        check=checks[name];assert check['ok'] and check['sha256_step']==previous['sha256_step']
        q=row['informe_motor']['resultado']['calidad'];bq=previous['informe_motor']['resultado']['calidad']
        for key in bq:assert q[key]==bq[key],(name,key)
        assert q['inspeccion_densa']['aceptado'] and q['autointerferencias_occ'] is False
        paths=[d/(Path(name).stem+'.step') for d in (a.referencia,a.resultados)]
        contents=[p.read_bytes() for p in paths]
        assert [hashlib.sha256(c).hexdigest() for c in contents]==[previous['sha256_step'],row['sha256_step']]
        data=[c.split(b'DATA;',1)[1] for c in contents];assert data[0]==data[1]
        repair=[p.with_suffix('.reparado.stl').read_bytes() for p in paths];assert repair[0]==repair[1]
        reports.append({'archivo':name,'ok':True,'data_step_identico_sha256':hashlib.sha256(data[0]).hexdigest(),
                        'sha256_step_anterior':previous['sha256_step'],'sha256_step_actual':row['sha256_step'],
                        'sha256_stl_original':row['sha256'],'sha256_stl_reparado':hashlib.sha256(repair[0]).hexdigest(),
                        'metricas_historicas_identicas':True,'nueva_inspeccion_densa':q['inspeccion_densa'],
                        'verificacion_independiente_previa':check})
    target=a.resultados/'identidad_geometria_previamente_verificada.json'
    target.write_text(json.dumps({'verificador_independiente_reejecutado':False,'motivo':'Identidad binaria de DATA STEP y STL, con prueba previa aprobada y comprobada por SHA256.','casos':reports},indent=2,ensure_ascii=False))
    print('4 casos: identidad de geometría STEP y STL certificada; pruebas independientes previas válidas para la misma geometría.')


if __name__=='__main__':main()
