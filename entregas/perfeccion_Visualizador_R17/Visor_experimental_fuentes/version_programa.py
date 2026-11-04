"""Identidad de esta copia experimental; independiente de la R7 instalada."""
from pathlib import Path
import hashlib
VERSION='R17 experimental'
COMPILACION='2026.11.04-perfiles-y-detalles'
PUERTO=8780

def identificador_instancia(root):
    path=str(Path(root).resolve())
    return hashlib.sha256(path.encode('utf-8')).hexdigest()[:20]

def identidad(root):
    return {'version':VERSION,'compilacion':COMPILACION,'instancia':identificador_instancia(root)}
