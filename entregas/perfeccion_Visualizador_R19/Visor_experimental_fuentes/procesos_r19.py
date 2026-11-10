"""Procesos acotados, logs en disco y terminación del árbol de trabajadores."""
from pathlib import Path
import os
import subprocess
import time
import psutil


def detener(proc):
    try:
        parent = psutil.Process(proc.pid)
        family = parent.children(recursive=True)
    except psutil.NoSuchProcess:
        family = []
    for child in reversed(family):
        try:
            child.kill()
        except psutil.NoSuchProcess:
            pass
    if proc.poll() is None:
        proc.kill()
    proc.wait(timeout=10)


def ejecutar(args, *, cwd, env, stdout, stderr, timeout, tick=None):
    stdout, stderr = map(Path, (stdout, stderr))
    with stdout.open('x', encoding='utf-8') as out, stderr.open('x', encoding='utf-8') as err:
        with subprocess.Popen(args, cwd=cwd, env=env, stdout=out, stderr=err) as proc:
            start = time.monotonic()
            try:
                while proc.poll() is None:
                    if time.monotonic() - start > timeout:
                        raise subprocess.TimeoutExpired(args, timeout)
                    if tick is not None:
                        tick()
                    time.sleep(.2)
                if tick is not None:
                    tick()
                return proc.returncode
            except BaseException:
                detener(proc)
                raise
