from collections.abc import Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, status
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Receive, Scope, Send

from app.api.access_control import router as access_control_router
from app.api.admin import router as admin_router
from app.api.agent_skills import router as agent_skills_router
from app.api.agents_md import router as agents_md_router
from app.api.auth import router as auth_router
from app.api.health import router as health_router
from app.api.images import admin_router as images_admin_router
from app.api.images import catalog_router
from app.api.instances import router as instances_router
from app.api.mcp_servers import router as mcp_servers_router
from app.api.public_config import router as public_config_router
from app.api.session_proxy import router as session_proxy_router
from app.api.ssh_identity import router as ssh_identity_router
from app.api.usage_metrics import router as usage_metrics_router
from app.bootstrap import ensure_admin
from app.config import Settings, get_settings
from app.db import connect, init_db
from app.runtime.docker_runtime import AioDockerContainerRuntime
from app.runtime.protocol import ContainerRuntime
from app.services.activity import ActivityTracker
from app.services.activity_flusher import run_activity_flusher
from app.services.agent_images import seed_agent_images
from app.services.background import cancel_all, spawn
from app.services.desktop_images import seed_desktop_images
from app.services.image_covers import seed_image_covers
from app.services.instances import backfill_open_runs
from app.services.login_throttle import LoginThrottle
from app.services.audit_log import install_handler
from app.services.reaper import reconcile_instance_states, run_reaper

# Cabeçalhos de segurança das respostas geradas pelo próprio portal (change
# http-hardening). `style-src 'unsafe-inline'` é requisito do MUI/Emotion,
# que injeta <style> inline; fontes, scripts e conexões são todas de origem
# própria (sem CDN), e `frame-src 'self'` cobre o iframe same-origin da
# sessão embutida.
_SECURITY_HEADERS: dict[str, str] = {
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "X-Frame-Options": "SAMEORIGIN",
    "Content-Security-Policy": (
        "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; font-src 'self'; connect-src 'self' ws: wss:; "
        "frame-src 'self'; frame-ancestors 'self'; object-src 'none'; base-uri 'self'"
    ),
}


class SecurityHeadersMiddleware:
    """Aplica `_SECURITY_HEADERS` às respostas do portal.

    O caminho do encaminhamento de sessão (`/i/...`) fica de fora: ali a
    resposta vem do container do usuário (streaming do proxy), e impor a
    política do portal ao conteúdo embutido poderia quebrar as UIs de
    desktop/terminal. `X-Frame-Options: SAMEORIGIN` (não DENY) porque o
    próprio portal embute esse iframe; `frame-ancestors 'self'` na CSP
    reforça o mesmo limite para navegadores modernos.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope.get("path", "").startswith("/i/"):
            await self.app(scope, receive, send)
            return

        async def send_with_headers(message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                for key, value in _SECURITY_HEADERS.items():
                    headers.append(key, value)
            await send(message)

        await self.app(scope, receive, send_with_headers)


def create_app(
    settings: Settings | None = None,
    runtime: ContainerRuntime | None = None,
    backend_resolver: Callable | None = None,
) -> FastAPI:
    """Fábrica da aplicação.

    Testes passam uma `Settings` própria (tipicamente apontando para um
    banco SQLite temporário), um `ContainerRuntime` falso e um
    `backend_resolver` apontando para um servidor de teste; em produção, o
    `main` do uvicorn usa a fábrica sem argumentos, a configuração vem do
    ambiente, o runtime real conversa com o Docker via `aiodocker`, e o
    proxy resolve o endereço do container pela rede Docker interna.
    """
    resolved_settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Construído aqui, não no corpo síncrono de create_app: aiodocker
        # abre seu conector sobre o event loop em execução, e create_app
        # roda na importação do módulo, antes de qualquer loop existir.
        resolved_runtime = runtime or AioDockerContainerRuntime()
        app.state.settings = resolved_settings
        app.state.runtime = resolved_runtime
        app.state.background_tasks = set()
        app.state.activity_tracker = ActivityTracker()
        app.state.login_throttle = LoginThrottle(
            max_failures=resolved_settings.login_max_failures,
            window_seconds=resolved_settings.login_window_seconds,
            lock_seconds=resolved_settings.login_lock_seconds,
        )
        if backend_resolver is not None:
            app.state.backend_resolver = backend_resolver

        resolved_settings.uploads_dir.mkdir(parents=True, exist_ok=True)

        # Trilha de eventos de segurança (change security-audit-log): uma
        # linha JSON por evento, na saída padrão.
        install_handler()

        conn = connect(resolved_settings.db_path)
        init_db(conn)
        ensure_admin(conn, resolved_settings)
        # Reconciliação uma vez no start (risco "worker é ponto único de
        # falha", design.md): recupera a visão correta depois de um
        # reinício do processo, caso containers tenham sido encerrados
        # por fora enquanto não havia ninguém observando.
        await reconcile_instance_states(conn, resolved_runtime)
        # Depois da reconciliação: uma instância que parecia "running" mas
        # já estava morta por fora já foi corrigida para "stopped" acima,
        # então só abre run retroativo para quem de fato segue em execução
        # (métricas de uso, D3/design.md).
        backfill_open_runs(conn)
        conn.close()

        # Garante a base e as 5 imagens de agente no catálogo. Aguarda os
        # builds (D8), mas cada falha é isolada e não impede o startup (D5).
        await seed_agent_images(resolved_settings, resolved_runtime)

        # Entradas de desktop padrão (change seed-desktop-images): pull em
        # segundo plano, antes do seed de capas — assim as capas padrão
        # (xfce/kde/mate/vscode) caem no mesmo boot do registro.
        seed_desktop_images(app, resolved_settings, resolved_runtime)

        # Capas padrão para toda entrada existente no catálogo: independe do
        # resultado do build e nunca sobrescreve capa enviada pelo admin.
        seed_image_covers(resolved_settings)

        spawn(
            app,
            run_activity_flusher(
                resolved_settings.db_path,
                app.state.activity_tracker,
                resolved_settings.activity_debounce_seconds,
            ),
        )
        spawn(
            app,
            run_reaper(
                resolved_settings.db_path,
                resolved_runtime,
                resolved_settings.idle_timeout_minutes,
                resolved_settings.reaper_interval_seconds,
                resolved_settings.session_purge_grace_hours,
            ),
        )

        yield

        await cancel_all(app)
        close = getattr(resolved_runtime, "close", None)
        if close is not None:
            await close()

    # Documentação interativa desligada por padrão (change http-hardening):
    # /docs, /redoc e /openapi.json expostos entregam o mapa completo da API
    # a anônimos; desenvolvimento liga com WCUI_DOCS_ENABLED=true.
    docs_kwargs = (
        {}
        if resolved_settings.docs_enabled
        else {"docs_url": None, "redoc_url": None, "openapi_url": None}
    )
    app = FastAPI(title="webcontainerui", lifespan=lifespan, **docs_kwargs)
    app.add_middleware(SecurityHeadersMiddleware)
    app.include_router(auth_router, prefix="/api/auth", tags=["auth"])
    app.include_router(admin_router, prefix="/api/admin", tags=["admin"])
    app.include_router(images_admin_router, prefix="/api/admin", tags=["admin", "images"])
    app.include_router(catalog_router, prefix="/api", tags=["catalog"])
    app.include_router(access_control_router, prefix="/api/admin", tags=["admin", "access-control"])
    app.include_router(usage_metrics_router, prefix="/api/admin", tags=["admin", "usage-metrics"])
    app.include_router(agents_md_router, prefix="/api/admin", tags=["admin", "agents-md"])
    app.include_router(agent_skills_router, prefix="/api/admin", tags=["admin", "agent-skills"])
    app.include_router(mcp_servers_router, prefix="/api/admin", tags=["admin", "mcp-servers"])
    app.include_router(instances_router, prefix="/api", tags=["instances"])
    app.include_router(ssh_identity_router, prefix="/api", tags=["ssh-identity"])
    app.include_router(public_config_router, prefix="/api", tags=["config"])
    app.include_router(health_router, tags=["health"])
    app.include_router(session_proxy_router, tags=["session-proxy"])

    # Imagens de capa enviadas pelo administrador (fora do bundle do
    # front-end, por isso um mount próprio em vez de reaproveitar /assets).
    # `check_dir=False`: a montagem das rotas é síncrona e roda antes do
    # lifespan, que é quem cria o diretório (mesmo padrão de `connect`
    # criando o diretório de `db_path`) — exigir que já exista aqui
    # quebraria a própria inicialização.
    app.mount(
        "/uploads",
        StaticFiles(directory=resolved_settings.uploads_dir, check_dir=False),
        name="uploads",
    )

    # Serve o build do front-end em "/", registrado por último para que
    # /api/* e /i/* (já registrados acima) tenham prioridade — a ordem de
    # registro é o que decide isso no roteamento do Starlette. Ausente em
    # desenvolvimento, onde é o Vite quem serve o front-end.
    if resolved_settings.frontend_dist.is_dir():
        assets_dir = resolved_settings.frontend_dist / "assets"
        if assets_dir.is_dir():
            app.mount("/assets", StaticFiles(directory=assets_dir), name="frontend-assets")

        index_path = resolved_settings.frontend_dist / "index.html"

        # Com a documentação interativa desligada, os paths dela não podem
        # cair no catch-all do SPA (serviriam index.html com 200); respondem
        # 404 como se não existissem (change http-hardening).
        _docs_paths = {"docs", "docs/oauth2-redirect", "redoc", "openapi.json"}

        @app.get("/{full_path:path}", include_in_schema=False)
        async def serve_spa(full_path: str) -> FileResponse:
            if full_path in _docs_paths and not resolved_settings.docs_enabled:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
            return FileResponse(index_path)

    return app


app = create_app()
