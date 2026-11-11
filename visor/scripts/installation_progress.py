"""Procesos del instalador con salida en vivo, registro y plazo acotado."""
from pathlib import Path
from contextlib import contextmanager
import os
import queue
import signal
import subprocess
import threading
import time


@contextmanager
def installation_lock(path):
    """El SO libera el bloqueo al cerrar una instalación interrumpida."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a+b') as stream:
        stream.seek(0, 2)
        if stream.tell() == 0:
            stream.write(b'0')
            stream.flush()
        stream.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            raise RuntimeError('Ya hay otra instalación R20 en ejecución. Usa su ventana y consulta el registro.') from error
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == 'nt':
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream, fcntl.LOCK_UN)


def stop_installation(process):
    if process.poll() is None:
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


def run_progress(command, *, cwd=None, env=None, log_path=None, label='Instalación',
                 timeout=600, heartbeat=10, echo=True):
    """Notificar silencios sin inventar porcentajes; detener el árbol al agotar plazo."""
    if timeout <= 0 or heartbeat <= 0:
        raise ValueError('Los plazos del instalador deben ser positivos')
    started = time.monotonic()
    process = subprocess.Popen(command, cwd=cwd, env=env, stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, text=True, encoding='utf-8',
                               errors='replace', start_new_session=True, bufsize=1)
    events = queue.Queue()

    def read_output():
        try:
            for line in process.stdout:
                events.put(line)
        finally:
            events.put(None)

    reader = threading.Thread(target=read_output, daemon=True)
    reader.start()
    log = None
    output = []

    def emit(line, force=False):
        if echo or force:
            print(line, end='', flush=True)
        if log:
            log.write(line)
            log.flush()

    try:
        if log_path:
            path = Path(log_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            log = path.open('a', encoding='utf-8')
        last_event = started
        while True:
            elapsed = time.monotonic() - started
            if elapsed >= timeout:
                raise TimeoutError(f'{label}: plazo de {timeout:g} s agotado; se detiene esta operación')
            try:
                line = events.get(timeout=min(.2, timeout - elapsed))
            except queue.Empty:
                now = time.monotonic()
                if process.poll() is None and now - last_event >= heartbeat:
                    emit(f'[EN CURSO] {label}; {now - started:.0f} s. El proceso sigue en ejecución.\n', force=True)
                    last_event = now
                continue
            if line is None:
                break
            output.append(line)
            emit(line)
            last_event = time.monotonic()
        remaining = max(.01, timeout - (time.monotonic() - started))
        code = process.wait(timeout=remaining)
        if code:
            raise RuntimeError(f'{label}: el proceso terminó con código {code}\n' + ''.join(output)[-2000:])
        return ''.join(output)
    except BaseException:
        stop_installation(process)
        raise
    finally:
        if log:
            log.close()
        reader.join(timeout=2)
        process.stdout.close()
