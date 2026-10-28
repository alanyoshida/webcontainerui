from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.db import connect
from app.runtime.errors import ContainerNotFoundError

router = APIRouter()


@router.get("/health", include_in_schema=False)
async def health(request: Request) -> JSONResponse:
    """Usado pela composição Docker para saber se o portal está pronto.

    Checa o banco (consulta trivial) e o runtime (uma chamada qualquer —
    `ContainerNotFoundError` já prova que o Docker respondeu; só uma
    falha de conexão de fato conta como runtime indisponível).
    """
    settings = request.app.state.settings

    db_ok = True
    try:
        conn = connect(settings.db_path)
        try:
            conn.execute("SELECT 1")
        finally:
            conn.close()
    except Exception:
        db_ok = False

    runtime_ok = True
    try:
        await request.app.state.runtime.inspect_container("__wcui_health_probe__")
    except ContainerNotFoundError:
        pass
    except Exception:
        runtime_ok = False

    healthy = db_ok and runtime_ok
    return JSONResponse(
        {
            "status": "ok" if healthy else "error",
            "database": "ok" if db_ok else "error",
            "runtime": "ok" if runtime_ok else "error",
        },
        status_code=200 if healthy else 503,
    )
