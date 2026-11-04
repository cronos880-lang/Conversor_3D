"""Intersecciones medidas para barridos, con curva UV y 3D coherentes."""
from recorte_exacto import recortar
import numpy as np
from OCP.Geom import Geom_Plane,Geom_SurfaceOfRevolution,Geom_SurfaceOfLinearExtrusion
from OCP.gp import gp_Pnt,gp_Pnt2d

def _desde_uv(surface,plane,uv_value,knots):
 from OCP.Geom2dAPI import Geom2dAPI_Interpolate
 from OCP.TColgp import TColgp_HArray1OfPnt2d
 from OCP.TColStd import TColStd_HArray1OfReal
 from OCP.Approx import Approx_CurveOnSurface
 from OCP.Geom2dAdaptor import Geom2dAdaptor_Curve
 from OCP.GeomAdaptor import GeomAdaptor_Surface
 from OCP.GeomAbs import GeomAbs_C1
 from pcurvas_compartidas import _error
 from geometria_medida import UV_KNOWN,registrar_uv
 n=np.array(plane.Axis().Direction().Coord());q=np.array(plane.Location().Coord());parameters=np.unique(np.r_[np.linspace(0,1,17),knots])
 parameters=np.r_[parameters[0],parameters[1:][np.diff(parameters)>1e-9]]
 if parameters[-1]<1.-1e-9:parameters=np.r_[parameters,1.]
 else:parameters[-1]=1.
 for iteration in range(12):
  uvpoints=np.array([uv_value(float(t)) for t in parameters]);uvpoints[:,0]=np.unwrap(uvpoints[:,0],period=surface.UPeriod()) if surface.IsUPeriodic() else uvpoints[:,0]
  points=TColgp_HArray1OfPnt2d(1,len(parameters));par=TColStd_HArray1OfReal(1,len(parameters))
  for i,(p,t) in enumerate(zip(uvpoints,parameters),1):points.SetValue(i,gp_Pnt2d(*map(float,p)));par.SetValue(i,float(t))
  fit=Geom2dAPI_Interpolate(points,par,False,1e-12);fit.Perform()
  if not fit.IsDone():raise ValueError(f"No se interpola UV: n={len(parameters)}, paso_min={np.diff(parameters).min()}")
  uv=fit.Curve();bad=[];maximum=0.
  for i,(a,b) in enumerate(zip(parameters[:-1],parameters[1:])):
   error=0.
   for t in np.linspace(a,b,9):
    p=uv.Value(float(t));xyz=np.array(surface.Value(p.X(),p.Y()).Coord());error=max(error,abs((xyz-q)@n))
   maximum=max(maximum,error)
   if error>1e-9:bad.append(i)
  if not bad:
   approx=Approx_CurveOnSurface(Geom2dAdaptor_Curve(uv),GeomAdaptor_Surface(surface),0.,1.,1e-10,GeomAbs_C1,8,1024,True,False)
   if not approx.HasResult() or approx.MaxError3d()>2e-8:raise ValueError('No se certifica la curva espacial del barrido')
   curve=approx.Curve3d();proof=_error(curve,uv,surface,0.,1.)
   if proof>5e-8:raise ValueError('El barrido no cumple la coherencia 2D/3D')
   registrar_uv(curve,surface,uv);print('INTERSECCION UV BARRIDA',len(parameters),'plano',maximum,'curva',proof,flush=True)
   return curve,0.,1.
  bad=np.array(bad,int);parameters=np.sort(np.r_[parameters,(parameters[bad]+parameters[bad+1])/2])
  if len(parameters)>4097:break
 raise ValueError('No converge la curva UV del barrido')

def interseccion(surface_a,surface_b,points,move,closed):
 crossed=interseccion_barridos_cruzados(surface_a,surface_b,points,move,closed)
 if crossed is not None:return crossed
 parallel=interseccion_barridos_paralelos(surface_a,surface_b,points,move,closed)
 if parallel is not None:return parallel
 angular=interseccion_angular(surface_a,surface_b,points,move,closed)
 if angular is not None:return angular
 cylindrical=interseccion_cilindrica(surface_a,surface_b,points,move,closed)
 if cylindrical is not None:return cylindrical
 exact=interseccion_afine(surface_a,surface_b,points,move,closed)
 if exact is not None:return exact
 native=interseccion_lineal(surface_a,surface_b,points,move,closed)
 if native is not None:return native
 planes=[s for s in (surface_a,surface_b) if isinstance(s,Geom_Plane)];sweeps=[s for s in (surface_a,surface_b) if isinstance(s,(Geom_SurfaceOfRevolution,Geom_SurfaceOfLinearExtrusion))]
 if len(planes)!=1 or len(sweeps)!=1 or closed:return None
 plane,surface=planes[0],sweeps[0];n=np.array(plane.Axis().Direction().Coord());p0=np.array(plane.Location().Coord())
 from OCP.ShapeAnalysis import ShapeAnalysis_Surface
 from OCP.GeomAPI import GeomAPI_ProjectPointOnCurve
 sas=__import__('proyeccion_barridos',fromlist=['analizador']).analizador(surface);seeds=[sas.ValueOfUV(gp_Pnt(*map(float,p)),1e-11).Coord() for p in points[[0,-1]]]
 if isinstance(surface,Geom_SurfaceOfRevolution):
  a=np.array(surface.Axis().Direction().Coord());q=np.array(surface.Axis().Location().Coord());dot=n@a
  if abs(dot)>.01:return None
  curve=surface.BasisCurve();v0,v1=seeds[0][1],seeds[1][1]
  if abs(v1-v0)<1e-8:return None
  u=n-dot*a;norm=np.linalg.norm(u);u/=norm;v=np.cross(a,u);sign=1 if np.median((points-q)@v)>=0 else -1
  def uv_value(t):
   param=v0+(v1-v0)*t;P=np.array(curve.Value(float(param)).Coord());z=(P-q)@a;radial=P-q-a*z;radius=np.linalg.norm(radial);base=radial/radius;cos=(n@(p0-q)-dot*z)/(radius*norm)
   if abs(cos)>1+1e-12:raise ValueError('No existe la sección del perfil de revolución')
   cos=np.clip(cos,-1,1);direction=u*cos+sign*v*np.sqrt(1-cos*cos);angle=np.arctan2(a@np.cross(base,direction),base@direction)
   return angle,param
  knots=[(curve.Knot(i)-v0)/(v1-v0) for i in range(1,curve.NbKnots()+1) if 0<(curve.Knot(i)-v0)/(v1-v0)<1]
 elif isinstance(surface,Geom_SurfaceOfLinearExtrusion):
  a=np.array(surface.Direction().Coord());dot=n@a
  if abs(dot)<1e-8:return None
  curve=surface.BasisCurve();u0,u1=seeds[0][0],seeds[1][0]
  if abs(u1-u0)<1e-8:return None
  def uv_value(t):
   u=u0+(u1-u0)*t;P=np.array(curve.Value(float(u)).Coord());return u,float(n@(p0-P)/dot)
  knots=[(curve.Knot(i)-u0)/(u1-u0) for i in range(1,curve.NbKnots()+1) if 0<(curve.Knot(i)-u0)/(u1-u0)<1]
 else:return None
 result=_desde_uv(surface,plane,uv_value,knots);curve,first,last=result
 errors=[GeomAPI_ProjectPointOnCurve(gp_Pnt(*map(float,p)),curve,first,last).LowerDistance() for p in points]
 if max(errors)>move:raise ValueError(f'La curva barrida queda lejos de su cadena fuente: {max(errors)}')
 return result

_LINE_CACHE={}
def lineas_compatibles(sa,sb):
 parallel=lineas_entre_barridos(sa,sb)
 if parallel:return [(p,a,u[0]) for p,a,u in parallel]
 planes=[s for s in (sa,sb) if isinstance(s,Geom_Plane)];sweeps=[s for s in (sa,sb) if isinstance(s,Geom_SurfaceOfLinearExtrusion)]
 if len(planes)!=1 or len(sweeps)!=1:return []
 plane,surface=planes[0],sweeps[0];key=(id(plane),id(surface))
 if key in _LINE_CACHE:return _LINE_CACHE[key][2]
 a=np.array(surface.Direction().Coord());n=np.array(plane.Axis().Direction().Coord());q=np.array(plane.Location().Coord())
 if abs(n@a)>1e-10:return []
 from scipy.optimize import brentq
 curve=surface.BasisCurve();ts=np.unique(np.r_[np.linspace(curve.FirstParameter(),curve.LastParameter(),257),[curve.Knot(i) for i in range(1,curve.NbKnots()+1)]])
 def fun(t):return float((np.array(curve.Value(float(t)).Coord())-q)@n)
 roots=[float(t) for t in ts if abs(fun(t))<1e-10]
 for lo,hi in zip(ts[:-1],ts[1:]):
  if fun(lo)*fun(hi)<0:roots.append(brentq(fun,lo,hi,xtol=1e-13))
 out=[]
 for t in roots:
  if abs(fun(t))<1e-10:out.append((np.array(curve.Value(t).Coord()),a,float(t)))
 _LINE_CACHE[key]=(plane,surface,out);return out

def interseccion_lineal(sa,sb,points,move,closed):
 if closed:return None
 lines=lineas_compatibles(sa,sb)
 if not lines:return None
 from OCP.Geom import Geom_Line
 from OCP.Geom2d import Geom2d_Line
 from OCP.gp import gp_Ax1,gp_Dir,gp_Ax2d,gp_Dir2d
 from geometria_medida import UV_KNOWN,registrar_uv
 surface=next(s for s in (sa,sb) if isinstance(s,Geom_SurfaceOfLinearExtrusion));best=None
 for origin,axis,parameter in lines:
  first,last=(points[[0,-1]]-origin)@axis
  lo,hi=min(first,last),max(first,last);projection=np.clip((points-origin)@axis,lo,hi);error=float(np.linalg.norm(origin+projection[:,None]*axis-points,axis=1).max())
  if best is None or error<best[0]:best=(error,origin,axis,parameter,first,last)
 error,origin,axis,parameter,first,last=best
 if error>move:raise ValueError('La generatriz no conserva la cadena fuente')
 sign=1.
 if last<first:axis=-axis;first,last=-first,-last;sign=-1.
 curve=Geom_Line(gp_Ax1(gp_Pnt(*map(float,origin)),gp_Dir(*map(float,axis))));uv=Geom2d_Line(gp_Ax2d(gp_Pnt2d(parameter,0.),gp_Dir2d(0.,sign)));registrar_uv(curve,surface,uv)
 return curve,float(first),float(last)

def interseccion_afine(sa,sb,points,move,closed):
 """Un corte oblicuo de una extrusión es una transformación AFÍN del perfil."""
 if closed:return None
 planes=[s for s in (sa,sb) if isinstance(s,Geom_Plane)];sweeps=[s for s in (sa,sb) if isinstance(s,Geom_SurfaceOfLinearExtrusion)]
 if len(planes)!=1 or len(sweeps)!=1:return None
 plane,surface=planes[0],sweeps[0];axis=np.array(surface.Direction().Coord());n=np.array(plane.Axis().Direction().Coord());q=np.array(plane.Location().Coord());dot=float(n@axis)
 if abs(dot)<=1e-10:return None
 from OCP.ShapeAnalysis import ShapeAnalysis_Surface
 from OCP.Geom import Geom_TrimmedCurve
 from OCP.GeomConvert import GeomConvert
 from OCP.Geom2d import Geom2d_BSplineCurve
 from OCP.TColgp import TColgp_Array1OfPnt2d
 from OCP.TColStd import TColStd_Array1OfReal,TColStd_Array1OfInteger
 from OCP.GeomAPI import GeomAPI_ProjectPointOnCurve
 from geometria_medida import UV_KNOWN,registrar_uv
 from pcurvas_compartidas import _error
 sas=__import__('proyeccion_barridos',fromlist=['analizador']).analizador(surface);u0,u1=[sas.ValueOfUV(gp_Pnt(*map(float,p)),1e-11).X() for p in points[[0,-1]]]
 if abs(u1-u0)<1e-10:return None
 lo,hi=sorted((u0,u1));curve=recortar(surface.BasisCurve(),lo,hi)
 if curve.IsRational():return None
 knots=[];K=TColStd_Array1OfReal(1,curve.NbKnots());M=TColStd_Array1OfInteger(1,curve.NbKnots());poles=TColgp_Array1OfPnt2d(1,curve.NbPoles());degree=curve.Degree()
 for i in range(1,curve.NbKnots()+1):K.SetValue(i,curve.Knot(i));M.SetValue(i,curve.Multiplicity(i));knots.extend([curve.Knot(i)]*curve.Multiplicity(i))
 for i in range(curve.NbPoles()):
  p=np.array(curve.Pole(i+1).Coord());v=float(n@(q-p)/dot);u=float(np.mean(knots[i+1:i+degree+1]));curve.SetPole(i+1,gp_Pnt(*map(float,p+axis*v)));poles.SetValue(i+1,gp_Pnt2d(u,v))
 uv=Geom2d_BSplineCurve(poles,K,M,degree,False)
 if u1<u0:curve.Reverse();uv.Reverse()
 error=_error(curve,uv,surface,lo,hi);plane_error=max(abs(n@(np.array(curve.Value(float(t)).Coord())-q)) for t in np.linspace(lo,hi,257))
 if error>5e-8 or plane_error>1e-9:raise ValueError('El corte afín no conserva sus soportes '+str(dict(error_uv=error,error_plano=plane_error,dot=dot,eje=axis.tolist(),normal=n.tolist())))
 if max(GeomAPI_ProjectPointOnCurve(gp_Pnt(*map(float,p)),curve,lo,hi).LowerDistance() for p in points)>move:raise ValueError('El corte afín queda fuera de la cadena fuente')
 registrar_uv(curve,surface,uv)
 return curve,float(lo),float(hi)

def _uv_por_tramos(surface,value,breaks,curve3d=None):
 """Aproximar sólo la función UV, respetando todos los nudos del perfil."""
 from OCP.Geom2d import Geom2d_BSplineCurve
 from OCP.TColgp import TColgp_Array1OfPnt2d
 from OCP.TColStd import TColStd_Array1OfReal,TColStd_Array1OfInteger
 from OCP.Approx import Approx_CurveOnSurface
 from OCP.Geom2dAdaptor import Geom2dAdaptor_Curve
 from OCP.GeomAdaptor import GeomAdaptor_Surface
 from OCP.GeomAbs import GeomAbs_C0
 from pcurvas_compartidas import _error
 from geometria_medida import UV_KNOWN,registrar_uv
 parts=[]
 def fit(lo,hi,depth=0):
  v=np.array([value(lo+(hi-lo)*t) for t in (0,1/3,2/3,1)])
  middle=np.linalg.solve(np.array([[4/9,2/9],[2/9,4/9]]),v[1:3]-np.array([[8/27,1/27],[1/27,8/27]])@v[[0,3]])
  P=np.array([v[0],middle[0],middle[1],v[-1]])
  error=0.
  for t in np.linspace(0,1,17):
   uv=P[0]*(1-t)**3+3*P[1]*(1-t)**2*t+3*P[2]*(1-t)*t*t+P[3]*t**3
   wanted=value(lo+(hi-lo)*t);error=max(error,float(np.linalg.norm(uv-wanted)))
  if error>1e-10:
   if depth>=20 or len(parts)>4000:raise ValueError('No converge la curva UV por tramos')
   mid=(lo+hi)/2;fit(lo,mid,depth+1);fit(mid,hi,depth+1)
  else:parts.append((lo,hi,P))
 for lo,hi in zip(breaks[:-1],breaks[1:]):fit(float(lo),float(hi))
 poles=TColgp_Array1OfPnt2d(1,3*len(parts)+1);knots=TColStd_Array1OfReal(1,len(parts)+1);mult=TColStd_Array1OfInteger(1,len(parts)+1);index=1
 for i,(lo,hi,P) in enumerate(parts):
  for p in P if i==0 else P[1:]:poles.SetValue(index,gp_Pnt2d(*map(float,p)));index+=1
  knots.SetValue(i+1,lo);mult.SetValue(i+1,4 if i==0 else 3)
 knots.SetValue(len(parts)+1,parts[-1][1]);mult.SetValue(len(parts)+1,4)
 uv=Geom2d_BSplineCurve(poles,knots,mult,3,False);lo,hi=float(breaks[0]),float(breaks[-1])
 from composicion_barridos import componer
 curve=curve3d if curve3d is not None else componer(surface,parts)
 if curve is None:
  approx=Approx_CurveOnSurface(Geom2dAdaptor_Curve(uv),GeomAdaptor_Surface(surface),lo,hi,1e-10,GeomAbs_C0,8,4096,True,False)
  if not approx.HasResult() or approx.MaxError3d()>2e-8:raise ValueError('No se certifica el corte espacial por tramos')
  curve=approx.Curve3d()
 error=_error(curve,uv,surface,lo,hi)
 if error>5e-8:raise ValueError('El corte por tramos no conserva su pcurva')
 registrar_uv(curve,surface,uv)
 print('CORTE UV POR TRAMOS',len(parts),'error',error,flush=True)
 return curve,lo,hi

def interseccion_cilindrica(sa,sb,points,move,closed):
 if closed:return None
 from OCP.Geom import Geom_CylindricalSurface
 planes=[s for s in (sa,sb) if isinstance(s,Geom_CylindricalSurface)];sweeps=[s for s in (sa,sb) if isinstance(s,Geom_SurfaceOfLinearExtrusion)]
 if len(planes)!=1 or len(sweeps)!=1:return None
 cylinder,surface=planes[0],sweeps[0];axis=np.array(surface.Direction().Coord());b=np.array(cylinder.Axis().Direction().Coord());q=np.array(cylinder.Location().Coord());radius=cylinder.Radius();a=axis-b*(axis@b);AA=float(a@a)
 if AA<1e-12:return None
 from OCP.ShapeAnalysis import ShapeAnalysis_Surface
 from OCP.GeomAPI import GeomAPI_ProjectPointOnCurve
 sas=__import__('proyeccion_barridos',fromlist=['analizador']).analizador(surface);seeds=np.array([sas.ValueOfUV(gp_Pnt(*map(float,p)),1e-11).Coord() for p in points]);u0,u1=seeds[[0,-1],0];curve=surface.BasisCurve()
 if abs(u1-u0)<1e-9:return None
 if np.max(seeds[:,0])>max(u0,u1)+1e-5 or np.min(seeds[:,0])<min(u0,u1)-1e-5:return None
 def roots(u):
  p=np.array(curve.Value(float(u)).Coord())-q;d=p-b*(p@b);B=2*float(a@d);C=float(d@d-radius*radius);disc=B*B-4*AA*C
  if disc<-1e-10:raise ValueError('El cilindro no corta el perfil medido')
  root=np.sqrt(max(0.,disc));return np.array([(-B-root)/(2*AA),(-B+root)/(2*AA)])
 mid=int(len(seeds)//2);branch=int(np.argmin(abs(roots(seeds[mid,0])-seeds[mid,1])))
 def value(t):
  u=u0+(u1-u0)*t;return np.array([u,roots(u)[branch]])
 breaks=np.unique(np.r_[0.,1.,[(curve.Knot(i)-u0)/(u1-u0) for i in range(1,curve.NbKnots()+1) if 0<(curve.Knot(i)-u0)/(u1-u0)<1]])
 out=_uv_por_tramos(surface,value,breaks);edge,lo,hi=out
 error=max(abs(np.linalg.norm(np.cross(np.array(edge.Value(float(t)).Coord())-q,b))-radius) for t in np.linspace(lo,hi,1025))
 if error>2e-8:raise ValueError('El corte no conserva el cilindro')
 if max(GeomAPI_ProjectPointOnCurve(gp_Pnt(*map(float,p)),edge,lo,hi).LowerDistance() for p in points)>move:raise ValueError('El corte cilíndrico no conserva la cadena fuente')
 return out

def interseccion_angular(sa,sb,points,move,closed):
 from OCP.Geom import Geom_CylindricalSurface
 cylinders=[s for s in (sa,sb) if isinstance(s,Geom_CylindricalSurface)];sweeps=[s for s in (sa,sb) if isinstance(s,Geom_SurfaceOfLinearExtrusion)]
 if len(cylinders)!=1 or len(sweeps)!=1 or closed:return None
 cylinder,surface=cylinders[0],sweeps[0];a=np.array(surface.Direction().Coord());b=np.array(cylinder.Axis().Direction().Coord());e=np.cross(a,b)
 if np.linalg.norm(e)<1e-6:return None
 e/=np.linalg.norm(e);q=np.array(cylinder.Location().Coord());x=np.array(cylinder.Position().XDirection().Coord());y=np.array(cylinder.Position().YDirection().Coord());radius=cylinder.Radius();D=points-q;theta=np.unwrap(np.arctan2(D@y,D@x));start,end=map(float,theta[[0,-1]])
 if abs(end-start)<1e-6:return None
 normalized=(theta-start)/(end-start)
 if np.min(np.diff(normalized))<-1e-5:return None
 from OCP.ShapeAnalysis import ShapeAnalysis_Surface
 from OCP.GeomAPI import GeomAPI_ProjectPointOnCurve
 from scipy.optimize import brentq
 from pcurvas_compartidas import _error
 from geometria_medida import UV_KNOWN,registrar_uv
 sas=__import__('proyeccion_barridos',fromlist=['analizador']).analizador(surface);seeds=np.array([sas.ValueOfUV(gp_Pnt(*map(float,p)),1e-11).X() for p in points]);curve=surface.BasisCurve();lo=max(curve.FirstParameter(),float(seeds.min())-.03);hi=min(curve.LastParameter(),float(seeds.max())+.03);perp=b-a*(b@a);den=float(perp@perp)
 sample_u=np.unique(np.r_[np.linspace(lo,hi,1025),[curve.Knot(i) for i in range(1,curve.NbKnots()+1) if lo<curve.Knot(i)<hi]]);sample_h=np.array([np.array(curve.Value(float(u)).Coord())@e for u in sample_u]);values_cache={}
 def value(t):
  if t in values_cache:return values_cache[t]
  angle=start+(end-start)*t;base=np.array(cylinder.Value(float(angle),0.).Coord());guess=float(np.interp(t,normalized,seeds));u=guess
  for _ in range(24):
   p=np.array(curve.Value(float(u)).Coord());f=float((p-base)@e)
   if abs(f)<1e-12:break
   derivative=float(np.array(curve.DN(float(u),1).Coord())@e)
   if abs(derivative)<1e-10:raise ValueError('Raíz tangente en el perfil del corte cilíndrico')
   candidate=u-f/derivative
   if not lo-1e-10<=candidate<=hi+1e-10:raise ValueError('El corte angular abandona su rama fuente')
   u=float(np.clip(candidate,lo,hi))
  if abs(f)>1e-11:
   level=float(base@e);brackets=np.flatnonzero((sample_h[:-1]-level)*(sample_h[1:]-level)<=0)
   if not len(brackets):raise ValueError('El corte angular no tiene raíz fuente')
   j=min(brackets,key=lambda j:abs((sample_u[j]+sample_u[j+1])*.5-guess));u=brentq(lambda u:float((np.array(curve.Value(float(u)).Coord())-base)@e),float(sample_u[j]),float(sample_u[j+1]),xtol=1e-13,rtol=1e-14)
  p=np.array(curve.Value(float(u)).Coord());w=float((p-base)@perp/den);result=np.array([angle,w]);values_cache[t]=result;return result
 # Los cambios de tramo del perfil se sitúan también en el parámetro angular.
 breaks=[0.,1.];A=radius*(x@e);B=radius*(y@e);amp=float(np.hypot(A,B));phase=float(np.arctan2(B,A))
 if amp>1e-10:
  for i in range(1,curve.NbKnots()+1):
   u=curve.Knot(i)
   if not lo<u<hi:continue
   level=float((np.array(curve.Value(u).Coord())-q)@e)/amp
   if abs(level)>1:continue
   for root in (phase+np.arccos(level),phase-np.arccos(level)):
    for shift in range(-5,6):
     angle=float(root+shift*2*np.pi);t=(angle-start)/(end-start)
     if 1e-8<t<1-1e-8 and abs(float(np.interp(t,normalized,seeds))-u)<.05:breaks.append(t)
 breaks=np.sort(np.asarray(breaks));breaks=np.r_[breaks[0],breaks[1:][np.diff(breaks)>1e-13]]
 result=_uv_por_tramos(cylinder,value,breaks);edge,first,last=result
 if max(GeomAPI_ProjectPointOnCurve(gp_Pnt(*map(float,p)),edge,first,last).LowerDistance() for p in points)>move:raise ValueError('El corte angular se aleja de su cadena fuente')
 # El segundo soporte se controla geométricamente antes de construir pcurvas.
 import meshfit_brep as base_module
 from geometria_medida import signed_projection
 samples=np.array([edge.Value(float(t)).Coord() for t in np.linspace(first,last,1025)]);error=float(abs(signed_projection(base_module._Proj(surface),samples)[0]).max())
 if error>2e-8:raise ValueError('El corte angular no conserva el perfil extruido')
 return result

_PARALLEL_CACHE={}
_RAICES_FUENTE={}
def registrar_generatriz_fuente(sa,sb,ua,ub):
 if sa is sb or not all(isinstance(s,Geom_SurfaceOfLinearExtrusion) for s in (sa,sb)):return
 a=np.array(sa.Direction().Coord());b=np.array(sb.Direction().Coord())
 if np.linalg.norm(np.cross(a,b))>1e-10:return
 pa=np.array(sa.BasisCurve().Value(float(ua)).Coord());pb=np.array(sb.BasisCurve().Value(float(ub)).Coord())
 error=float(np.linalg.norm(np.cross(pa-pb,a)))
 if error>1e-9:return
 for first,second,origin,axis,parameters in ((sa,sb,pa,a,(ua,ub)),(sb,sa,pb,b,(ub,ua))):
  key=(id(first),id(second));items=_RAICES_FUENTE.setdefault(key,(first,second,[]))[2]
  if not any(np.linalg.norm(np.cross(origin-q,axis))<1e-10 and np.linalg.norm(np.array(parameters)-np.array(ts))<1e-10 for q,ax,ts in items):items.append((origin.copy(),axis.copy(),tuple(map(float,parameters))))
  _PARALLEL_CACHE.pop(key,None)

def lineas_entre_barridos(sa,sb):
 if not all(isinstance(s,Geom_SurfaceOfLinearExtrusion) for s in (sa,sb)):return []
 a=np.array(sa.Direction().Coord());b=np.array(sb.Direction().Coord())
 if np.linalg.norm(np.cross(a,b))>1e-10:return []
 key=(id(sa),id(sb))
 if key in _PARALLEL_CACHE:return _PARALLEL_CACHE[key][2]
 from OCP.Geom2d import Geom2d_BSplineCurve
 from OCP.Geom2dAPI import Geom2dAPI_InterCurveCurve
 from OCP.TColgp import TColgp_Array1OfPnt2d
 from OCP.TColStd import TColStd_Array1OfReal,TColStd_Array1OfInteger
 helper=np.eye(3)[np.argmin(abs(a))];e=np.cross(a,helper);e/=np.linalg.norm(e);f=np.cross(a,e)
 def projected(curve):
  if curve.IsRational():raise ValueError('Perfil racional no admitido en el corte paralelo')
  P=TColgp_Array1OfPnt2d(1,curve.NbPoles());K=TColStd_Array1OfReal(1,curve.NbKnots());M=TColStd_Array1OfInteger(1,curve.NbKnots())
  for i in range(1,curve.NbPoles()+1):
   p=np.array(curve.Pole(i).Coord());P.SetValue(i,gp_Pnt2d(float(p@e),float(p@f)))
  for i in range(1,curve.NbKnots()+1):K.SetValue(i,curve.Knot(i));M.SetValue(i,curve.Multiplicity(i))
  return Geom2d_BSplineCurve(P,K,M,curve.Degree(),False)
 ca,cb=sa.BasisCurve(),sb.BasisCurve();qa,qb=projected(ca),projected(cb);result=list(_RAICES_FUENTE.get(key,(None,None,[]))[2])
 try:
  intersection=Geom2dAPI_InterCurveCurve(qa,qb,1e-10)
  for i in range(1,intersection.NbPoints()+1):
   point=intersection.Point(i)
   from OCP.Geom2dAPI import Geom2dAPI_ProjectPointOnCurve
   pa_uv=Geom2dAPI_ProjectPointOnCurve(point,qa);pb_uv=Geom2dAPI_ProjectPointOnCurve(point,qb)
   if not pa_uv.NbPoints() or not pb_uv.NbPoints():continue
   ua,ub=pa_uv.LowerDistanceParameter(),pb_uv.LowerDistanceParameter();origin=e*point.X()+f*point.Y()
   pa=np.array(ca.Value(float(ua)).Coord());pb=np.array(cb.Value(float(ub)).Coord())
   if np.linalg.norm(np.cross(pa-pb,a))>5e-8:continue
   result.append((origin,a,(float(ua),float(ub))))
 except Exception:pass
 # Una tangencia en un nudo puede no ser devuelta por el intersector de OCC.
 # Contrastar esos puntos con la curva contraria y conservar sólo coincidencias
 # dentro de la MISMA coherencia geométrica exigida después a la pcurva.
 from OCP.Geom2dAPI import Geom2dAPI_ProjectPointOnCurve
 for first,second,which in [(qa,qb,0),(qb,qa,1)]:
  for j in range(1,first.NbKnots()+1):
   u=first.Knot(j);p=first.Value(u)
   try:
    projection=Geom2dAPI_ProjectPointOnCurve(p,second)
    if projection.NbPoints()==0 or projection.LowerDistance()>2e-8:continue
    v=projection.LowerDistanceParameter();other=second.Value(v);origin=e*((p.X()+other.X())*.5)+f*((p.Y()+other.Y())*.5);parameters=(u,v) if which==0 else (v,u)
    if not any(np.linalg.norm(origin-r[0])<1e-8 for r in result):result.append((origin,a,tuple(map(float,parameters))))
   except Exception:continue
 print('GENERATRICES ENTRE PERFILES',len(result),flush=True)
 _PARALLEL_CACHE[key]=(sa,sb,result);return result

def interseccion_barridos_paralelos(sa,sb,points,move,closed):
 if closed:return None
 candidates=lineas_entre_barridos(sa,sb)
 if not candidates:return None
 from OCP.Geom import Geom_Line
 from OCP.Geom2d import Geom2d_Line
 from OCP.gp import gp_Ax1,gp_Ax2d,gp_Dir2d,gp_Dir
 from geometria_medida import UV_KNOWN,registrar_uv
 best=None
 for origin,axis,parameters in candidates:
  first,last=(points[[0,-1]]-origin)@axis;lo,hi=sorted((first,last));t=np.clip((points-origin)@axis,lo,hi);error=float(np.linalg.norm(origin+np.outer(t,axis)-points,axis=1).max())
  if best is None or error<best[0]:best=(error,origin,axis,parameters,first,last)
 error,origin,axis,parameters,first,last=best
 if error>move:raise ValueError('La generatriz paralela abandona la cadena fuente')
 if last<first:axis=-axis;first,last=-first,-last
 curve=Geom_Line(gp_Ax1(gp_Pnt(*map(float,origin)),gp_Dir(*map(float,axis))))
 for surface,u in zip((sa,sb),parameters):
  direction=np.array(surface.Direction().Coord());base=np.array(surface.BasisCurve().Value(u).Coord());v=float((origin-base)@direction);sign=float(axis@direction);registrar_uv(curve,surface,Geom2d_Line(gp_Ax2d(gp_Pnt2d(u,v),gp_Dir2d(0.,sign))))
 return curve,float(first),float(last)

def interseccion_barridos_cruzados(sa,sb,points,move,closed):
 # Una carta puede tener una raíz cuadrada en un extremo aunque la curva
 # espacial sea perfectamente regular. Probar ambos soportes como parámetro.
 errors=[]
 for reverse,(first,second) in enumerate(((sa,sb),(sb,sa))):
  try:
   result=_interseccion_barridos_cruzados_carta(first,second,points,move,closed)
   if result is not None:
    if reverse:print('CARTA INVERSA DE PERFILES VERIFICADA',flush=True)
    return result
  except ValueError as exc:errors.append(str(exc))
 if errors:
  import os,json,hashlib
  from pathlib import Path
  target=os.environ.get('PILOTO_CORTES_DIR')
  if target:
   serial=[]
   for surface in (sa,sb):
    curve=surface.BasisCurve();serial.append(dict(eje=surface.Direction().Coord(),grado=curve.Degree(),periodica=curve.IsPeriodic(),racional=curve.IsRational(),polos=[curve.Pole(i).Coord() for i in range(1,curve.NbPoles()+1)],nudos=[curve.Knot(i) for i in range(1,curve.NbKnots()+1)],multiplicidades=[curve.Multiplicity(i) for i in range(1,curve.NbKnots()+1)]))
   data=dict(superficies=serial,puntos=points.tolist(),movimiento_mm=move,cerrada=closed,errores=errors);content=json.dumps(data,indent=2);folder=Path(target);folder.mkdir(parents=True,exist_ok=True);(folder/(hashlib.sha256(content.encode()).hexdigest()[:12]+'.json')).write_text(content)
  raise ValueError('No convergen las cartas de los perfiles cruzados: '+str(errors))
 return None

def _interseccion_barridos_cruzados_carta(sa,sb,points,move,closed):
 """El encuentro de dos perfiles extruidos se resuelve por su coordenada común."""
 if closed or not all(isinstance(s,Geom_SurfaceOfLinearExtrusion) for s in (sa,sb)):return None
 a=np.array(sa.Direction().Coord());b=np.array(sb.Direction().Coord());dot=float(a@b);det=1-dot*dot
 if det<1e-8:return None
 e=np.cross(a,b);e/=np.linalg.norm(e);ca,cb=sa.BasisCurve(),sb.BasisCurve()
 from proyeccion_barridos import uv_exacta
 from scipy.optimize import brentq
 from geometria_medida import UV_KNOWN,registrar_uv
 from pcurvas_compartidas import _error
 seeds_a=uv_exacta(sa,points)[:,0];seeds_b=uv_exacta(sb,points)[:,0];u0,u1=map(float,seeds_a[[0,-1]])
 if abs(u1-u0)<1e-9:return None
 normalized=(seeds_a-u0)/(u1-u0)
 if np.min(np.diff(normalized))<-1e-5:return None
 lo=max(cb.FirstParameter(),float(seeds_b.min())-.03);hi=min(cb.LastParameter(),float(seeds_b.max())+.03)
 sb_parameters=np.unique(np.r_[np.linspace(lo,hi,513),[cb.Knot(i) for i in range(1,cb.NbKnots()+1) if lo<cb.Knot(i)<hi]]);sb_height=np.array([np.array(cb.Value(float(u)).Coord())@e for u in sb_parameters]);cache={}
 def evaluate(t):
  if t in cache:return cache[t]
  u=u0+(u1-u0)*t;P=np.array(ca.Value(float(u)).Coord());level=float(P@e);guess=float(np.interp(t,normalized,seeds_b));delta=sb_height-level;near=np.flatnonzero(abs(delta)<1e-11)
  if len(near):v=float(sb_parameters[min(near,key=lambda j:abs(sb_parameters[j]-guess))])
  else:
   brackets=np.flatnonzero(delta[:-1]*delta[1:]<0)
   if not len(brackets):raise ValueError('Los perfiles cruzados no tienen una raíz fuente común')
   j=min(brackets,key=lambda j:abs((sb_parameters[j]+sb_parameters[j+1])*.5-guess));v=brentq(lambda v:float(np.array(cb.Value(float(v)).Coord())@e-level),float(sb_parameters[j]),float(sb_parameters[j+1]),xtol=1e-13,rtol=1e-14)
  Q=np.array(cb.Value(float(v)).Coord());D=Q-P;va=float((D@a-dot*(D@b))/det);vb=float((dot*(D@a)-D@b)/det);cache[t]=(np.array([u,va]),np.array([v,vb]));return cache[t]
 breaks=[0.,1.]+[(ca.Knot(i)-u0)/(u1-u0) for i in range(1,ca.NbKnots()+1) if 0<(ca.Knot(i)-u0)/(u1-u0)<1]
 at=np.unique(np.r_[np.linspace(min(u0,u1),max(u0,u1),513),[ca.Knot(i) for i in range(1,ca.NbKnots()+1) if min(u0,u1)<ca.Knot(i)<max(u0,u1)]]);ah=np.array([np.array(ca.Value(float(u)).Coord())@e for u in at])
 for i in range(1,cb.NbKnots()+1):
  v=cb.Knot(i)
  if not lo<v<hi:continue
  level=float(np.array(cb.Value(v).Coord())@e);delta=ah-level
  for j in np.flatnonzero(delta[:-1]*delta[1:]<0):
   u=brentq(lambda u:float(np.array(ca.Value(float(u)).Coord())@e-level),float(at[j]),float(at[j+1]),xtol=1e-13,rtol=1e-14);t=(u-u0)/(u1-u0)
   if 1e-8<t<1-1e-8:breaks.append(t)
 breaks=np.sort(np.asarray(breaks));breaks=np.r_[breaks[0],breaks[1:][np.diff(breaks)>1e-13]]
 curve,first,last=_uv_por_tramos(sa,lambda t:evaluate(t)[0],breaks)
 second,_,_=_uv_por_tramos(sb,lambda t:evaluate(t)[1],breaks,curve3d=curve);uv=UV_KNOWN[id(second),id(sb)];error=_error(curve,uv,sb,first,last)
 if error>5e-8:raise ValueError('El encuentro de perfiles no comparte la misma curva espacial')
 registrar_uv(curve,sb,uv)
 from OCP.GeomAPI import GeomAPI_ProjectPointOnCurve
 if max(GeomAPI_ProjectPointOnCurve(gp_Pnt(*map(float,p)),curve,first,last).LowerDistance() for p in points)>move:raise ValueError('El encuentro de perfiles abandona la fuente')
 print('ENCUENTRO DE PERFILES CRUZADOS',error,flush=True);return curve,first,last
