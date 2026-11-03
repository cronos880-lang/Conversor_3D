"""Diagnóstico JSON independiente. No modifica el STL.

python diagnosticar_stl.py pieza.stl --completo --salida informe.json
El modo completo comprueba autointerferencias con OCC y contactos/solapamientos.
Tiene los límites de tamaño de la unión experimental; informa si no se ejecutó.
"""
import argparse
import hashlib
import json
from pathlib import Path
from preprocesador_stl import cargar_exacto, diagnosticar, componentes, _manifold


def diagnostico_completo(mesh):
    from verificacion_reparacion import solido_poliedrico
    report = diagnosticar(mesh)
    parts = componentes(mesh)
    if len(mesh.faces) > 20_000 or len(parts) > 8:
        report['autointersecciones'] = 'no evaluadas: supera límite experimental 20.000 caras / 8 cuerpos'
        report['completo'] = False
        return report
    if not all(p.is_watertight and p.is_winding_consistent and p.volume > 0 for p in parts):
        report['autointersecciones'] = 'no evaluadas: hay componentes abiertos o mal orientados'
        report['completo'] = False
        return report
    report['completo'] = True
    try:
        for p in parts:
            solido_poliedrico(p)
        report['autointersecciones'] = 'OpenCascade BRepAlgoAPI_Check no detecta interferencias'
        solids = [_manifold(p) for p in parts]
        contacts = []
        for i, a in enumerate(solids):
            for j in range(i+1, len(solids)):
                b = solids[j]
                volume = (a ^ b).volume()
                union = a+b
                contact_area = max(0., (a.surface_area()+b.surface_area()-union.surface_area())/2)
                contacts.append({'componentes': [i, j], 'interseccion_mm3': volume,
                                 'area_contacto_o_interior_mm2': contact_area,
                                 'separacion_acotada_mm': a.min_gap(b, .020),
                                 'tipo': 'solapamiento' if volume > 1e-9 else
                                         'contacto_superficial' if contact_area > 1e-9 else
                                         'separados_o_contacto_sin_area'})
        report['contactos'] = contacts
    except Exception as exc:
        report.update(autointersecciones='no se pudo validar: '+str(exc),
                      ruta='rechazar_interferencia_o_ambiguedad', gravedad='error')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stl', type=Path)
    parser.add_argument('--completo', action='store_true')
    parser.add_argument('--salida', type=Path)
    args = parser.parse_args()
    mesh = cargar_exacto(args.stl)
    data = diagnostico_completo(mesh) if args.completo else diagnosticar(mesh)
    data['sha256'] = hashlib.sha256(args.stl.read_bytes()).hexdigest()
    text = json.dumps(data, ensure_ascii=False, indent=2)
    if args.salida:
        args.salida.write_text(text, encoding='utf-8')
    print(text)
    return 1 if data['gravedad'] == 'error' else 0


if __name__ == '__main__':
    raise SystemExit(main())
