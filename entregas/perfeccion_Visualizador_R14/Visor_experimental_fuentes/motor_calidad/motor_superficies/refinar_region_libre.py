"""Subdivisión adaptativa de una región libre que no conserva sus contornos."""
from recorte_exacto import recortar
class RefinarRegionLibre(ValueError):
    def __init__(self,region,motivo):
        super().__init__(motivo);self.region=int(region)

def guardar(region,edges,points,loops):
    import os,json,hashlib
    from pathlib import Path
    from OCP.Geom import Geom_TrimmedCurve
    from OCP.GeomConvert import GeomConvert
    folder=os.environ.get('PILOTO_CORTES_DIR')
    if not folder:return
    curves=[]
    for curve,first,last in edges:
        c=recortar(curve,float(first),float(last))
        curves.append(dict(grado=c.Degree(),periodica=c.IsPeriodic(),polos=[c.Pole(i).Coord() for i in range(1,c.NbPoles()+1)],pesos=[c.Weight(i) for i in range(1,c.NbPoles()+1)],nudos=[c.Knot(i) for i in range(1,c.NbKnots()+1)],multiplicidades=[c.Multiplicity(i) for i in range(1,c.NbKnots()+1)],first=c.FirstParameter(),last=c.LastParameter()))
    record=dict(region=region,contornos=loops,curvas=curves,puntos=points.tolist());content=json.dumps(record,indent=2);target=Path(folder);target.mkdir(parents=True,exist_ok=True);(target/('parche_'+hashlib.sha256(content.encode()).hexdigest()[:12]+'.json')).write_text(content)
