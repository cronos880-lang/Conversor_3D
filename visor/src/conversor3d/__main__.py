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
    conversion = subcommands.add_parser('convert', help='Convertir con validación completa final')
    conversion.add_argument('source', type=Path)
    conversion.add_argument('destination', type=Path)
    server = subcommands.add_parser('serve', help='Abrir el Visor de desarrollo')
    server.add_argument('--port', type=int, default=8783)
    server.add_argument('--no-browser', action='store_true')
    args = parser.parse_args()
    if args.command == 'propose':
        from .geometry import propose
        print(json.dumps(propose(args.baseline, args.destination), ensure_ascii=False))
    elif args.command == 'convert':
        from .pipeline import convert
        try:
            value = convert(args.source, args.destination)
        except Exception as error:
            import traceback
            traceback.print_exc()
            print(json.dumps({'ok': False, 'error': str(error)}, ensure_ascii=True))
            return 2
        print(json.dumps(value, ensure_ascii=True))
    elif args.command == 'serve':
        from .server import serve
        serve(args.port, not args.no_browser)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
