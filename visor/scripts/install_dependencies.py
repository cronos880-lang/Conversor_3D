"""Instalar el entorno de desarrollo con versiones y hashes completos por plataforma."""
from pathlib import Path
import os
import platform
import subprocess
import sys

root = Path(__file__).resolve().parents[1]
if sys.version_info[:2] != (3, 12) or platform.machine().lower() not in ('amd64', 'x86_64'):
    raise SystemExit('Se requiere CPython 3.12 x64 para estos locks comprobados')
if sys.platform not in ('win32', 'linux'):
    raise SystemExit('Los locks actuales cubren Windows y Linux')
lock = root / ('requirements-windows-py312.lock' if os.name == 'nt' else 'requirements-linux-py312.lock')
subprocess.run([sys.executable, '-m', 'pip', 'install', '--require-hashes', '--only-binary=:all:', '-r', str(lock)], check=True)
subprocess.run([sys.executable, '-m', 'pip', 'install', '-e', str(root), '--no-deps', '--no-build-isolation'], check=True)
subprocess.run([sys.executable, '-m', 'pip', 'check'], check=True)
