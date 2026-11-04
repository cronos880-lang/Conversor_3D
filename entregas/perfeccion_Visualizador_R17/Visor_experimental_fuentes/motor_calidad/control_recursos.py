"""Vigilar el proceso CAD ya aislado; sin crear otro motor ni relajar límites.

Ideas de meshfit_guard adaptadas al árbol del servidor y a cancelación existente.
"""
from __future__ import annotations
import os
import subprocess
import time
import psutil


class LimiteRecursos(RuntimeError):
    def __init__(self, message, stdout='', stderr='', pico_mb=0, codigo='limite_recursos'):
        super().__init__(message)
        self.stdout, self.stderr, self.pico_mb = stdout, stderr, pico_mb
        self.codigo=codigo


def limite_memoria_bytes():
    # Límite absoluto conservador y mitad de RAM disponible al iniciar.
    # En Linux respetar además cgroup v2 del entorno de referencia.
    total = psutil.virtual_memory().total
    try:
        from pathlib import Path
        value = Path('/sys/fs/cgroup/memory.max').read_text().strip()
        if value != 'max':
            total = min(total, int(value))
    except (OSError, ValueError):
        pass
    return min(6*1024**3, int(total*.5))


def comunicar_vigilado(proc, timeout, detener, *, memoria_bytes=None, politica=None, informar=None):
    cap = limite_memoria_bytes() if memoria_bytes is None else memoria_bytes
    if timeout <= 0 or cap <= 0:
        raise ValueError('Límites de recursos inválidos.')
    start, peak = time.monotonic(), 0
    process = psutil.Process(proc.pid)
    maximum=float(politica['maximo_s']) if politica else float(timeout)
    deadline=min(float(timeout),maximum)
    previous_cpu=0.;last_cpu_sample=start;last_activity=start-60;ram=0
    last_report=start;cpu_rate=0.
    activity_window=min(10.,max(.05,float(timeout)*.25))
    while True:
        try:
            family=[p for p in [process,*process.children(recursive=True)] if p.is_running()]
            ram = sum(p.memory_info().rss for p in family)
            times=[p.cpu_times() for p in family]
            cpu=sum(t.user+t.system for t in times)
            cpu_now=time.monotonic()
            cpu_rate=max(0.,(cpu-previous_cpu)/max(cpu_now-last_cpu_sample,.001))
            if cpu_rate>.1:
                last_activity=cpu_now
            previous_cpu=cpu
            last_cpu_sample=cpu_now
            peak = max(peak, ram)
        except psutil.NoSuchProcess:
            pass
        except psutil.AccessDenied as exc:
            detener(proc)
            out, err = proc.communicate()
            raise LimiteRecursos('No se puede supervisar la memoria del motor; detenido.', out, err, peak/1024**2) from exc
        elapsed=time.monotonic()-start
        if informar and time.monotonic()-last_report>=2:
            informar({'plazo_actual_s':deadline,'maximo_s':maximum,
                      'cpu_activa':time.monotonic()-last_activity<activity_window,
                      'consumo_cpu_porcentaje':round(100*cpu_rate,1),
                      'ram_pico_mb':round(peak/1024**2,1)})
            last_report=time.monotonic()
        if (politica and elapsed>deadline and deadline<maximum
                and time.monotonic()-last_activity<activity_window):
            deadline=min(maximum,deadline+politica.get('incremento_s',30))
            if informar:informar({'plazo_actual_s':deadline,'maximo_s':maximum,
                                  'segundos_cpu':round(previous_cpu,2),'motivo':'El motor sigue trabajando.'})
        why = (f'Límite de tiempo: {elapsed:.0f} s; plazo {deadline:.0f} s, máximo {maximum:.0f} s. '
               'No se ha obtenido un STEP aprobado; no es una medición de error dimensional.' if elapsed>deadline else
               f'La conversión se detuvo por memoria: {peak/1024**2:.0f} MB > {cap/1024**2:.0f} MB.' if peak > cap else None)
        if why:
            detener(proc)
            out, err = proc.communicate()
            raise LimiteRecursos(why, out, err, peak/1024**2,
                                 codigo='tiempo_agotado' if elapsed>deadline else 'memoria_agotada')
        try:
            out, err = proc.communicate(timeout=min(.5, max(.01, deadline-(time.monotonic()-start))))
            return out, err, round(peak/1024**2, 2)
        except subprocess.TimeoutExpired:
            continue
