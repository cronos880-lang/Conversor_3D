"""Controles de origen antes de interpretar formularios o iniciar trabajos."""
from starlette.responses import JSONResponse


class LocalAccessMiddleware:
    def __init__(self, app, port: int):
        self.app = app
        self.hosts = {f'127.0.0.1:{port}', f'localhost:{port}'}
        self.origins = {f'http://{host}' for host in self.hosts}

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            await self.app(scope, receive, send)
            return
        headers = {}
        for name, value in scope.get('headers', []):
            headers.setdefault(name.lower(), []).append(value)
        try:
            hosts = headers.get(b'host', [])
            valid_host = len(hosts) == 1 and hosts[0].decode('ascii').lower() in self.hosts
        except UnicodeDecodeError:
            valid_host = False
        if not valid_host:
            await JSONResponse({'detail': 'Host no permitido para este Visor local'}, status_code=400)(scope, receive, send)
            return
        origins = headers.get(b'origin', [])
        if origins:
            try:
                allowed = len(origins) == 1 and origins[0].decode('ascii') in self.origins
            except UnicodeDecodeError:
                allowed = False
            if not allowed:
                await JSONResponse({'detail': 'Origen no permitido'}, status_code=403)(scope, receive, send)
                return
        site = headers.get(b'sec-fetch-site', [b''])[0]
        if scope['method'] not in ('GET', 'HEAD', 'OPTIONS') and site == b'cross-site':
            await JSONResponse({'detail': 'Petición de otra web rechazada'}, status_code=403)(scope, receive, send)
            return
        await self.app(scope, receive, send)
