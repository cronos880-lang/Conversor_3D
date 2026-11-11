"""Procesos nativos acotados: un timeout detiene también los descendientes."""
from pathlib import Path
import os
import signal
import subprocess
import time


def stop_tree(process):
    if process.poll() is not None:
        return
    if os.name == 'nt':
        subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15)
        if process.poll() is None:
            process.kill()
    else:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    process.wait(timeout=15)


def execute(command, folder: Path, name: str, *, cwd=None, env=None, timeout=540):
    folder = Path(folder)
    start = time.monotonic()
    with (folder / (name + '.stdout.txt')).open('xb') as out, (folder / (name + '.stderr.txt')).open('xb') as err:
        process = subprocess.Popen(command, cwd=cwd, env=env, stdout=out, stderr=err,
                                   start_new_session=True)
        try:
            code = process.wait(timeout=timeout)
        except BaseException:
            stop_tree(process)
            raise
    return {'returncode': code, 'seconds': time.monotonic() - start}
