"""Geometría de perfiles medidos en un trabajador aislado.

Reconstruye las mismas superficies y sus aristas comunes, conservando primero
las estrategias aprobadas R9. Rechaza superficies libres; no las faceta.
Toda propuesta requiere lectura fría, geometría, material y tres mallados.
No cambia los umbrales de aceptación del Visor.
"""
from pathlib import Path
import sys, math, json, time, collections, os
import numpy as np, cadquery as cq
from scipy.optimize import least_squares
from OCP.BRep import BRep_Builder, BRep_Tool
from OCP.BRepAdaptor import BRepAdaptor_Curve, BRepAdaptor_Surface
from OCP.BRepTools import BRepTools_WireExplorer
from OCP.TopoDS import TopoDS, TopoDS_Edge, TopoDS_Vertex, TopoDS_Face, TopoDS_Wire, TopoDS_Shell
from OCP.TopAbs import TopAbs_FORWARD, TopAbs_REVERSED
from OCP.TopExp import TopExp
from OCP.TopTools import TopTools_IndexedMapOfShape
from OCP.Geom import Geom_Plane, Geom_CylindricalSurface, Geom_TrimmedCurve, Geom_SurfaceOfRevolution, Geom_BSplineSurface, Geom_ToroidalSurface, Geom_Circle, Geom_SurfaceOfLinearExtrusion
from OCP.gp import gp_Pnt, gp_Vec2d, gp_Dir, gp_Pln
import meshfit_brep as base
import contornos_compatibles as cc
from contornos_compatibles import _interseccion, _sobre_superficie
from pcurvas_compartidas import crear_pcurva as original_pcurva, _error
from fijacion_contornos import AjusteContornos
from OCP.BRepCheck import BRepCheck_Analyzer
UV_KNOWN = {}

def extend_profile(curve, margin=0.03):
    if curve.Degree() != 3 or curve.IsRational():
        raise ValueError('Perfil no cúbico polinómico')
    from OCP.Geom import Geom_BSplineCurve
    from OCP.TColgp import TColgp_Array1OfPnt
    from OCP.TColStd import TColStd_Array1OfReal, TColStd_Array1OfInteger
    lo, hi = (curve.FirstParameter(), curve.LastParameter())
    parts = []
    for a, b, base_t in ((lo - margin, lo, lo), (hi, hi + margin, hi)):
        p = np.array(curve.Value(base_t).Coord())
        d1 = np.array(curve.DN(base_t, 1).Coord())
        d2 = np.array(curve.DN(base_t, 2).Coord())
        d3 = np.array(curve.DN(base_t, 3).Coord())
        delta = a - base_t
        v0 = p + delta * d1 + delta ** 2 * d2 / 2 + delta ** 3 * d3 / 6
        v1 = d1 + delta * d2 + delta ** 2 * d3 / 2
        v2 = d2 + delta * d3
        h = b - a
        points = [v0, v0 + h * v1 / 3, v0 + 2 * h * v1 / 3 + h * h * v2 / 6, v0 + h * v1 + h * h * v2 / 2 + h ** 3 * d3 / 6]
        poles = TColgp_Array1OfPnt(1, 4)
        for i, x in enumerate(points, 1):
            poles.SetValue(i, gp_Pnt(*map(float, x)))
        knots = TColStd_Array1OfReal(1, 2)
        mult = TColStd_Array1OfInteger(1, 2)
        for i, t in enumerate((a, b), 1):
            knots.SetValue(i, t)
            mult.SetValue(i, 4)
        parts.append(Geom_BSplineCurve(poles, knots, mult, 3, False))
    pieces = [parts[0], curve, parts[1]]
    allp = []
    allk = []
    allm = []
    for j, part in enumerate(pieces):
        if j:
            allm[-1] = 3
        for i in range(1 + int(j > 0), part.NbPoles() + 1):
            allp.append(part.Pole(i))
        for i in range(1 + int(j > 0), part.NbKnots() + 1):
            allk.append(part.Knot(i))
            allm.append(part.Multiplicity(i))
    P = TColgp_Array1OfPnt(1, len(allp))
    K = TColStd_Array1OfReal(1, len(allk))
    M = TColStd_Array1OfInteger(1, len(allm))
    for i, p in enumerate(allp, 1):
        P.SetValue(i, p)
    for i, (k, m) in enumerate(zip(allk, allm), 1):
        K.SetValue(i, k)
        M.SetValue(i, m)
    result = Geom_BSplineCurve(P, K, M, 3, False)
    delta = max((curve.Value(float(t)).Distance(result.Value(float(t))) for t in np.linspace(lo, hi, 257)))
    if delta > 1e-10:
        raise ValueError('Extensión altera el perfil original')
    print('PERFIL EXTENDIDO', result.FirstParameter(), result.LastParameter(), 'cambio', delta, flush=True)
    return result

def crear_pcurva(curve, first, last, surface):
    known = UV_KNOWN.get((id(curve), id(surface)))
    if known is not None:
        error = _error(curve, known, surface, first, last)
        if error <= 5e-08:
            return (known.Copy(), dict(max_desacuerdo_mm=error, uv_generadora=True))
        raise ValueError(f'Curva UV generadora no certificada {error}')
    try:
        return original_pcurva(curve, first, last, surface)
    except ValueError as initial:
        if not isinstance(surface, (Geom_SurfaceOfRevolution, Geom_SurfaceOfLinearExtrusion, Geom_BSplineSurface)):
            raise
        from OCP.ShapeAnalysis import ShapeAnalysis_Surface
        from OCP.Geom2dAPI import Geom2dAPI_Interpolate
        from OCP.TColgp import TColgp_HArray1OfPnt2d
        from OCP.TColStd import TColStd_HArray1OfReal
        from OCP.gp import gp_Pnt2d
        sas = __import__('proyeccion_barridos',fromlist=['analizador']).analizador(surface)
        from pcurvas_compartidas import _iso_comun
        from OCP.GeomAPI import GeomAPI_ProjectPointOnCurve
        iso = _iso_comun(curve, first, last, surface)
        parameters = np.linspace(first, last, 33)
        if hasattr(curve, 'NbKnots'):
            parameters = np.unique(np.r_[parameters, [curve.Knot(i) for i in range(1, curve.NbKnots() + 1) if first < curve.Knot(i) < last]])
        for attempt in range(14):
            if iso is None:
                points = np.array([sas.ValueOfUV(curve.Value(float(t)), 1e-11).Coord() for t in parameters])
            else:
                geometry, dim, value, lo, hi = iso
                points = []
                for t in parameters:
                    target = curve.Value(float(t))
                    pr = GeomAPI_ProjectPointOnCurve(target, geometry, lo, hi)
                    if not pr.NbPoints():
                        raise ValueError('No se verifica la isocurva')
                    variable = pr.LowerDistanceParameter()
                    for _ in range(16):
                        delta = np.array(geometry.Value(variable).Coord()) - np.array(target.Coord())
                        if np.linalg.norm(delta) < 1e-11:
                            break
                        d1 = np.array(geometry.DN(variable, 1).Coord())
                        d2 = np.array(geometry.DN(variable, 2).Coord())
                        hessian = d1 @ d1 + delta @ d2
                        if hessian <= 1e-24:
                            break
                        candidate = float(np.clip(variable - delta @ d1 / hessian, lo, hi))
                        if candidate == variable:
                            break
                        variable = candidate
                    points.append((value, variable) if dim == 0 else (variable, value))
                points = np.asarray(points)
            if surface.IsUPeriodic():
                points[:, 0] = np.unwrap(points[:, 0], period=surface.UPeriod())
            if surface.IsVPeriodic():
                points[:, 1] = np.unwrap(points[:, 1], period=surface.VPeriod())
            count = len(parameters)
            arr = TColgp_HArray1OfPnt2d(1, count)
            par = TColStd_HArray1OfReal(1, count)
            for i, (p, t) in enumerate(zip(points, parameters), 1):
                arr.SetValue(i, gp_Pnt2d(*map(float, p)))
                par.SetValue(i, float(t))
            fit = Geom2dAPI_Interpolate(arr, par, False, 1e-12)
            fit.Perform()
            uv = fit.Curve()
            bad = []
            maximum = 0.0
            for i, (a, b) in enumerate(zip(parameters[:-1], parameters[1:])):
                error = 0.0
                for t in np.linspace(a, b, 9):
                    p = uv.Value(float(t))
                    error = max(error, curve.Value(float(t)).Distance(surface.Value(p.X(), p.Y())))
                maximum = max(maximum, error)
                if error > 3e-08:
                    bad.append(i)
            print('UV ADAPTATIVA', count, maximum, flush=True)
            if maximum < 3e-08:
                verified = _error(curve, uv, surface, first, last)
                if verified <= 5e-08:
                    return (uv, dict(max_desacuerdo_mm=verified, adaptativa=True))
                raise ValueError(f'Control UV global falla {verified}')
            if len(parameters) > 4097:
                break
            bad = np.array(bad, int)
            parameters = np.sort(np.r_[parameters, (parameters[bad] + parameters[bad + 1]) * 0.5])
        raise initial

def compact_projection(oldcurve, lo, hi, surface, pts):
    from OCP.GeomConvert import GeomConvert
    if isinstance(surface, Geom_Plane):
        c = GeomConvert.CurveToBSplineCurve_s(Geom_TrimmedCurve(oldcurve, lo, hi))
        pr = base._Proj(surface)
        P = np.array([c.Pole(i).Coord() for i in range(1, c.NbPoles() + 1)])
        P = pr.batch(P)
        P[0] = pts[0]
        P[-1] = pts[-1]
        for i, p in enumerate(P, 1):
            c.SetPole(i, gp_Pnt(*map(float, p)))
        return (c, c.FirstParameter(), c.LastParameter())
    from OCP.ShapeAnalysis import ShapeAnalysis_Surface
    from OCP.Geom2dAPI import Geom2dAPI_Interpolate
    from OCP.TColgp import TColgp_HArray1OfPnt2d
    from OCP.TColStd import TColStd_HArray1OfReal
    from OCP.gp import gp_Pnt2d
    from OCP.Approx import Approx_CurveOnSurface
    from OCP.Geom2dAdaptor import Geom2dAdaptor_Curve
    from OCP.GeomAdaptor import GeomAdaptor_Surface
    from OCP.GeomAbs import GeomAbs_C1
    sas = __import__('proyeccion_barridos',fromlist=['analizador']).analizador(surface)
    uvpoints = np.array([sas.ValueOfUV(gp_Pnt(*map(float, p)), 1e-11).Coord() for p in pts])
    if surface.IsUPeriodic():
        uvpoints[:, 0] = np.unwrap(uvpoints[:, 0], period=surface.UPeriod())
    if surface.IsVPeriodic():
        uvpoints[:, 1] = np.unwrap(uvpoints[:, 1], period=surface.VPeriod())
    arr = TColgp_HArray1OfPnt2d(1, len(pts))
    par = TColStd_HArray1OfReal(1, len(pts))
    for i, (p, t) in enumerate(zip(uvpoints, np.linspace(lo, hi, len(pts))), 1):
        arr.SetValue(i, gp_Pnt2d(*map(float, p)))
        par.SetValue(i, float(t))
    fit = Geom2dAPI_Interpolate(arr, par, False, 1e-12)
    fit.Perform()
    uv = fit.Curve()
    app = Approx_CurveOnSurface(Geom2dAdaptor_Curve(uv), GeomAdaptor_Surface(surface), lo, hi, 1e-10, GeomAbs_C1, 8, 128, True, False)
    if not app.HasResult() or app.MaxError3d() > 2e-08:
        raise ValueError('No converge la proyección compacta')
    c = app.Curve3d()
    error = _error(c, uv, surface, lo, hi)
    if error > 5e-08:
        raise ValueError('No se certifica la proyección compacta')
    UV_KNOWN[id(c), id(surface)] = uv
    print('PROYECCION COMPACTA', c.NbPoles(), error, flush=True)
    return (c, lo, hi)

def signed_projection(pr, points):
    from proyeccion_barridos import residual
    projected=residual(pr.s,points,pr.sas) if isinstance(pr.s,Geom_SurfaceOfLinearExtrusion) else None
    if projected is not None:return projected
    if pr.kind in ('plane', 'cyl', 'sph'):
        return cc._residual_normal(pr, points)
    if pr.kind == 'tor':
        d = points - pr.q
        z = d @ pr.a
        radial = d - z[:, None] * pr.a
        rho = np.linalg.norm(radial, axis=1)
        direction = radial / np.maximum(rho[:, None], 1e-30)
        minor = d - pr.R * direction
        length = np.linalg.norm(minor, axis=1)
        return (length - pr.r, minor / np.maximum(length[:, None], 1e-30))
    from OCP.GeomLProp import GeomLProp_SLProps
    values = []
    normals = []
    for point in points:
        uv = pr.sas.ValueOfUV(gp_Pnt(*map(float, point)), 1e-10)
        props = GeomLProp_SLProps(pr.s, uv.X(), uv.Y(), 1, 1e-12)
        if not props.IsNormalDefined():
            raise ValueError('Normal de revolución indeterminada')
        n = np.array(props.Normal().Coord())
        projected = np.array(pr.s.Value(uv.X(), uv.Y()).Coord())
        values.append((point - projected) @ n)
        normals.append(n)
    return (np.array(values), np.array(normals))
old_refine = cc.refinar_interseccion

def refine_generic(curve, first, last, sa, sb, max_move):
    if not any((isinstance(s, (Geom_SurfaceOfRevolution,Geom_SurfaceOfLinearExtrusion)) for s in (sa, sb))):
        return old_refine(curve, first, last, sa, sb, max_move)
    from OCP.TColgp import TColgp_HArray1OfPnt
    from OCP.TColStd import TColStd_HArray1OfReal
    from OCP.GeomAPI import GeomAPI_Interpolate
    projectors = [base._Proj(s) for s in (sa, sb)]
    endpoints=np.array([curve.Value(float(t)).Coord() for t in (first,last)])
    pinned=max(float(abs(signed_projection(p,endpoints)[0]).max()) for p in projectors)<=1e-9
    parameters = np.linspace(first, last, 33)
    for iteration in range(14):
        count = len(parameters)
        initial = np.array([curve.Value(float(t)).Coord() for t in parameters])
        points = initial.copy()
        for _ in range(20):
            f, n = signed_projection(projectors[0], points)
            g, m = signed_projection(projectors[1], points)
            if max(abs(f).max(), abs(g).max()) < 1e-10:
                break
            dot = np.sum(n * m, axis=1)
            det = 1 - dot * dot
            if np.any((det < 1e-10) & (np.maximum(abs(f), abs(g)) > 1e-09)):
                raise ValueError('Encuentro de revolución tangente inestable')
            det = np.maximum(det, 1e-10)
            points -= ((f - dot * g) / det)[:, None] * n + ((g - dot * f) / det)[:, None] * m
        if pinned:points[[0,-1]]=endpoints
        if np.linalg.norm(points - initial, axis=1).max() > max_move:
            raise ValueError('Corrección de revolución fuera de presupuesto')
        array = TColgp_HArray1OfPnt(1, count)
        params = TColStd_HArray1OfReal(1, count)
        for j, (p, t) in enumerate(zip(points, parameters), 1):
            array.SetValue(j, gp_Pnt(*map(float, p)))
            params.SetValue(j, float(t))
        fit = GeomAPI_Interpolate(array, params, False, 1e-12)
        fit.Perform()
        result = fit.Curve()
        ts = np.concatenate([np.linspace(a, b, 9) for a, b in zip(parameters[:-1], parameters[1:])])
        probes = np.array([result.Value(float(t)).Coord() for t in ts])
        residual = np.maximum(abs(signed_projection(projectors[0], probes)[0]), abs(signed_projection(projectors[1], probes)[0]))
        error = residual.max()
        print('REFINAMIENTO REVOLUCION', count, error, flush=True)
        if error < 2e-08:
            return (result, first, last)
        bad = np.flatnonzero(residual.reshape(-1, 9).max(axis=1) > 2e-08)
        parameters = np.sort(np.r_[parameters, (parameters[bad] + parameters[bad + 1]) / 2])
        if len(parameters) > 4097:
            break
    raise ValueError('No converge la curva de revolución compartida '+str([(type(s).__name__,s.Axis().Direction().Coord() if hasattr(s,'Axis') else s.Direction().Coord(),s.Radius() if hasattr(s,'Radius') else 0) for s in (sa,sb)]))

def circle_supports(sa, sb):
    # Corte perpendicular de un perfil medido de revolución. También incluye
    # contactos tangentes en los extremos del perfil, sin inflar tolerancias.
    revs = [s for s in (sa, sb) if isinstance(s, Geom_SurfaceOfRevolution)]
    planes = [s for s in (sa, sb) if isinstance(s, Geom_Plane)]
    if len(revs) == len(planes) == 1:
        from scipy.optimize import brentq
        rev, plane = revs[0], planes[0]
        axis = np.array(rev.Axis().Direction().Coord())
        origin = np.array(rev.Axis().Location().Coord())
        n = np.array(plane.Axis().Direction().Coord())
        if np.linalg.norm(np.cross(n, axis)) < 1e-10:
            height = n @ (np.array(plane.Location().Coord()) - origin) / (n @ axis)
            curve = rev.BasisCurve()
            ts = np.unique(np.r_[np.linspace(curve.FirstParameter(), curve.LastParameter(), 257), [curve.Knot(i) for i in range(1, curve.NbKnots()+1)]])
            def value(t): return (np.array(curve.Value(float(t)).Coord()) - origin) @ axis - height
            roots = [float(t) for t in ts if abs(value(t)) < 1e-10]
            for a, b in zip(ts[:-1], ts[1:]):
                if value(a)*value(b) < 0: roots.append(brentq(value, a, b, xtol=1e-13))
            result = []
            for t in roots:
                point = np.array(curve.Value(float(t)).Coord())
                radius = np.linalg.norm(np.cross(point-origin, axis))
                if radius > 1e-8 and abs(value(t)) < 1e-10:
                    result.append((origin+axis*height, axis, radius))
            return result
    tori = [s for s in (sa, sb) if isinstance(s, Geom_ToroidalSurface)]
    if len(tori) != 1:
        return []
    tor = tori[0]
    other = sb if tor is sa else sa
    axis = np.array(tor.Axis().Direction().Coord())
    q = np.array(tor.Location().Coord())
    major, minor = (tor.MajorRadius(), tor.MinorRadius())
    results = []
    if isinstance(other, Geom_Plane):
        n = np.array(other.Axis().Direction().Coord())
        if np.linalg.norm(np.cross(n, axis)) > 1e-10:
            return []
        h = (np.array(other.Location().Coord()) - q) @ axis
        delta = minor * minor - h * h
        if delta < -1e-13:
            return []
        for r in np.unique([major - np.sqrt(max(delta, 0)), major + np.sqrt(max(delta, 0))]):
            results.append((q + axis * h, axis, float(r)))
    if isinstance(other, Geom_CylindricalSurface):
        a = np.array(other.Axis().Direction().Coord())
        c = np.array(other.Location().Coord())
        if np.linalg.norm(np.cross(a, axis)) > 1e-10 or np.linalg.norm(np.cross(c - q, axis)) > 1e-09:
            return []
        radius = other.Radius()
        delta = minor * minor - (radius - major) ** 2
        if delta < -1e-13:
            return []
        for h in np.unique([-np.sqrt(max(delta, 0)), np.sqrt(max(delta, 0))]):
            results.append((q + axis * h, axis, radius))
    return results

def tangent_line_supports(sa, sb):
    planes = [s for s in (sa, sb) if isinstance(s, Geom_Plane)]
    cyl = [s for s in (sa, sb) if isinstance(s, Geom_CylindricalSurface)]
    if len(planes) != 1 or len(cyl) != 1:
        return None
    p, cy = (planes[0], cyl[0])
    n = np.array(p.Axis().Direction().Coord())
    a = np.array(cy.Axis().Direction().Coord())
    q = np.array(cy.Location().Coord())
    origin = np.array(p.Location().Coord())
    d = (q - origin) @ n
    if abs(n @ a) > 1e-10 or abs(abs(d) - cy.Radius()) > 1e-09:
        return None
    return (q - n * d, a)

def intersection_stable(sa, sb, pts, move, closed):
    from curvas_barridas import interseccion
    measured = interseccion(sa,sb,pts,move,closed)
    if measured is not None: return measured
    circles = circle_supports(sa, sb)
    if circles:
        from OCP.gp import gp_Ax2
        from OCP.GeomAPI import GeomAPI_ProjectPointOnCurve
        proposals = []
        for center, axis, radius in circles:
            helper = np.eye(3)[np.argmin(abs(axis))]
            x = np.cross(axis, helper)
            x /= np.linalg.norm(x)
            y = np.cross(axis, x)
            curve = Geom_Circle(gp_Ax2(gp_Pnt(*map(float, center)), gp_Dir(*map(float, axis)), gp_Dir(*map(float, x))), radius)
            phi = np.unwrap(np.arctan2((pts - center) @ y, (pts - center) @ x))
            first, last = (phi[0], phi[-1])
            if closed:
                last = first + np.copysign(2 * np.pi, last - first)
            if last < first:
                first, last = (curve.ReversedParameter(first), curve.ReversedParameter(last))
                curve = curve.Reversed()
            error = max((GeomAPI_ProjectPointOnCurve(gp_Pnt(*map(float, p)), curve).LowerDistance() for p in pts))
            if error <= move:
                proposals.append((error, curve, float(first), float(last)))
        if not proposals:
            raise ValueError('Círculo de encuentro alejado del contorno')
        _, curve, first, last = min(proposals, key=lambda p: p[0])
        return (curve, first, last)
    if isinstance(sa, Geom_Plane) and isinstance(sb, Geom_Plane) and (not closed):
        from OCP.Geom import Geom_Line
        from OCP.gp import gp_Ax1
        n = np.array(sa.Axis().Direction().Coord())
        m = np.array(sb.Axis().Direction().Coord())
        axis = np.cross(n, m)
        if np.linalg.norm(axis) > 1e-08:
            axis /= np.linalg.norm(axis)
            q = np.linalg.solve(np.vstack((n, m, axis)), [n @ np.array(sa.Location().Coord()), m @ np.array(sb.Location().Coord()), axis @ pts.mean(0)])
            first, last = (pts[[0, -1]] - q) @ axis
            if last < first:
                axis = -axis
                first, last = (-first, -last)
            projection = np.clip((pts - q) @ axis, first, last)
            error = np.linalg.norm(q + projection[:, None] * axis - pts, axis=1).max()
            if error > move or last - first < 1e-10:
                raise ValueError(f'Contorno plano no verificable {error}')
            return (Geom_Line(gp_Ax1(gp_Pnt(*map(float, q)), gp_Dir(*map(float, axis)))), float(first), float(last))
    if any((isinstance(s, (Geom_SurfaceOfRevolution,Geom_SurfaceOfLinearExtrusion)) for s in (sa, sb))):
        from OCP.TColgp import TColgp_HArray1OfPnt
        from OCP.TColStd import TColStd_HArray1OfReal
        from OCP.GeomAPI import GeomAPI_Interpolate
        count = len(pts)
        arr = TColgp_HArray1OfPnt(1, count)
        par = TColStd_HArray1OfReal(1, count)
        for i, (p, t) in enumerate(zip(pts, np.linspace(0, 1, count)), 1):
            arr.SetValue(i, gp_Pnt(*map(float, p)))
            par.SetValue(i, float(t))
        fit = GeomAPI_Interpolate(arr, par, False, 1e-12)
        fit.Perform()
        return refine_generic(fit.Curve(), 0.0, 1.0, sa, sb, move)
    planes = [s for s in (sa, sb) if isinstance(s, Geom_Plane)]
    cylinders = [s for s in (sa, sb) if isinstance(s, Geom_CylindricalSurface)]
    if len(planes) == len(cylinders) == 1 and (not closed):
        pl = planes[0]
        cy = cylinders[0]
        n = np.array(pl.Axis().Direction().Coord())
        a = np.array(cy.Axis().Direction().Coord())
        q = np.array(cy.Location().Coord())
        p = np.array(pl.Location().Coord())
        dot = n @ a
        z = (pts - q) @ a
        if abs(dot) < 0.01 and np.ptp(z) > 1e-05:
            u = n - dot * a
            norm = np.linalg.norm(u)
            u /= norm
            v = np.cross(a, u)
            sign = 1 if np.median((pts - q) @ v) >= 0 else -1
            radius = cy.Radius()
            first = float(z[0])
            last = float(z[-1])

            def value(t):
                axial = first + (last - first) * t
                cos = (n @ (p - q) - dot * axial) / (radius * norm)
                if abs(cos) > 1 + 1e-12:
                    raise ValueError('No existe la sección plano-cilindro')
                cos = np.clip(cos, -1, 1)
                return q + a * axial + radius * (u * cos + sign * v * np.sqrt(1 - cos * cos))
            from OCP.TColgp import TColgp_HArray1OfPnt
            from OCP.TColStd import TColStd_HArray1OfReal
            from OCP.GeomAPI import GeomAPI_Interpolate, GeomAPI_ProjectPointOnCurve
            for count in (17, 33, 65, 129, 257):
                array = TColgp_HArray1OfPnt(1, count)
                parameters = TColStd_HArray1OfReal(1, count)
                for j, t in enumerate(np.linspace(0, 1, count), 1):
                    array.SetValue(j, gp_Pnt(*map(float, value(t))))
                    parameters.SetValue(j, float(t))
                fit = GeomAPI_Interpolate(array, parameters, False, 1e-12)
                fit.Perform()
                curve = fit.Curve()
                error = max((curve.Value(float(t)).Distance(gp_Pnt(*map(float, value(t)))) for t in np.linspace(0, 1, count * 4)))
                if error < 2e-08:
                    if max((GeomAPI_ProjectPointOnCurve(gp_Pnt(*map(float, x)), curve).LowerDistance() for x in pts)) > move:
                        raise ValueError('Intersección estable lejos del contorno')
                    print('SECCION CASI PARALELA', count, error, flush=True)
                    return (curve, 0.0, 1.0)
    if len(cylinders) == 2 and (not closed):
        a, b = cylinders
        axis = np.array(a.Axis().Direction().Coord())
        axis_b = np.array(b.Axis().Direction().Coord())
        q = np.array(a.Location().Coord())
        qb = np.array(b.Location().Coord())
        r = a.Radius()
        rb = b.Radius()
        z = (pts - q) @ axis
        if np.linalg.norm(np.cross(axis, axis_b)) < 0.0001 and np.ptp(z) > 1e-05:
            x = np.array(a.Position().XDirection().Coord())
            y = np.array(a.Position().YDirection().Coord())
            radial = pts - q - z[:, None] * axis
            theta = np.unwrap(np.arctan2(radial @ y, radial @ x))
            first, last = (float(z[0]), float(z[-1]))

            def value(t):
                h = first + (last - first) * t
                angle = theta[0] + t * (theta[-1] - theta[0])
                for _ in range(20):
                    point = q + axis * h + r * (x * np.cos(angle) + y * np.sin(angle))
                    d = point - qb
                    d -= axis_b * (d @ axis_b)
                    f = d @ d - rb * rb
                    if abs(f) < 1e-11:
                        return point
                    deriv = r * (-x * np.sin(angle) + y * np.cos(angle))
                    df = 2 * (d @ deriv)
                    if abs(df) < 1e-10:
                        raise ValueError('Encuentro tangente inestable')
                    step = f / df
                    if abs(step) > 0.1:
                        raise ValueError('Cambio de rama cilíndrica')
                    angle -= step
                raise ValueError('No converge la sección entre cilindros')
            from OCP.TColgp import TColgp_HArray1OfPnt
            from OCP.TColStd import TColStd_HArray1OfReal
            from OCP.GeomAPI import GeomAPI_Interpolate, GeomAPI_ProjectPointOnCurve
            for count in (17, 33, 65, 129, 257):
                array = TColgp_HArray1OfPnt(1, count)
                parameters = TColStd_HArray1OfReal(1, count)
                for j, t in enumerate(np.linspace(0, 1, count), 1):
                    array.SetValue(j, gp_Pnt(*map(float, value(t))))
                    parameters.SetValue(j, float(t))
                fit = GeomAPI_Interpolate(array, parameters, False, 1e-12)
                fit.Perform()
                curve = fit.Curve()
                error = max((curve.Value(float(t)).Distance(gp_Pnt(*map(float, value(t)))) for t in np.linspace(0, 1, count * 4)))
                if error < 2e-08:
                    if max((GeomAPI_ProjectPointOnCurve(gp_Pnt(*map(float, p)), curve).LowerDistance() for p in pts)) > move:
                        raise ValueError('Intersección cilíndrica lejos del contorno')
                    print('CILINDROS CASI PARALELOS', count, error, flush=True)
                    return (curve, 0.0, 1.0)
    return _interseccion(sa, sb, pts, move, closed)

def normalizar_circulos(shape):
    """Misma parametrización y eje; sólo elipses circulares a 1e-12 mm.

    Evita extremos locales espurios de OCC al medir el borde de un cilindro.
    No transforma elipses genuinas ni cambia tolerancias de aristas.
    """
    from OCP.Geom import Geom_Ellipse, Geom_Circle
    builder = BRep_Builder()
    count = 0
    for edge in shape.Edges():
        adaptor = BRepAdaptor_Curve(edge.wrapped)
        curve = BRep_Tool.Curve_s(edge.wrapped, adaptor.FirstParameter(), adaptor.LastParameter())
        if isinstance(curve, Geom_Ellipse) and abs(curve.MajorRadius()-curve.MinorRadius()) < 1e-12:
            builder.UpdateEdge(edge.wrapped, Geom_Circle(curve.Position(), curve.MajorRadius()),
                               BRep_Tool.Tolerance_s(edge.wrapped))
            count += 1
    return count
