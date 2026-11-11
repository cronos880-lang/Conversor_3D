"""Herramientas del Visor en desarrollo, sin alterar la entrega R19."""
import argparse
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subcommands = parser.add_subparsers(dest='command', required=True)
    proposal = subcommands.add_parser('propose', help='Crear candidato pendiente de validación')
    proposal.add_argument('baseline', type=Path)
    proposal.add_argument('destination', type=Path)
    args = parser.parse_args()
    if args.command == 'propose':
        from .geometry import propose
        print(json.dumps(propose(args.baseline, args.destination), ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
