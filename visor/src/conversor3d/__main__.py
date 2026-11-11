"""Herramientas del Visor en desarrollo, sin alterar la entrega R19."""
import argparse
import json
from pathlib import Path
from ._version import APPLICATION_LABEL, __version__


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--version', action='version', version=APPLICATION_LABEL + ' ' + __version__)
    subcommands = parser.add_subparsers(dest='command', required=True)
    proposal = subcommands.add_parser('propose', help='Crear candidato pendiente de validación')
    proposal.add_argument('baseline', type=Path)
    proposal.add_argument('destination', type=Path)
    conversion = subcommands.add_parser('convert', help='Convertir con validación completa final')
    conversion.add_argument('source', type=Path)
    conversion.add_argument('destination', type=Path)
    server = subcommands.add_parser('serve', help='Abrir el Visor de desarrollo')
    server.add_argument('--port', type=int)
    subcommands.add_parser('config', help='Mostrar ajustes y unidades')
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
            print(json.dumps({'ok': False, 'error': str(error),
                              'tipo_error': getattr(error, 'code', type(error).__name__)}, ensure_ascii=True))
            return 2
        print(json.dumps(value, ensure_ascii=True))
    elif args.command == 'config':
        from .settings import Settings
        print(json.dumps(Settings.read().describe(), ensure_ascii=False, indent=2))
    elif args.command == 'serve':
        from .server import serve
        serve(args.port, not args.no_browser)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
