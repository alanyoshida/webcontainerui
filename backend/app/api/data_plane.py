"""Autorização interna do plano de dados externo (change external-stream-proxy).

O Caddy consulta este endpoint por `forward_auth` antes de encaminhar cada
requisição (e a abertura do canal persistente) de `/i/{uuid}/` ao container.
A resposta aprovada carrega a credencial da instância num cabeçalho que o
`forward_auth` copia para a requisição encaminhada — o cliente nunca a vê.

A requisição chega como GET com o método e a URI originais preservados em
`X-Forwarded-Method`/`X-Forwarded-Uri` (é o que o `forward_auth` faz: reescreve
a URI para este endpoint e encaminha os originais em cabeçalhos).
"""

import base64
import hmac
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from app.config import Settings
from app.deps import SESSION_COOKIE_NAME, get_db
from app.services.errors import NotFoundError
from app.services.instances import get_owned_instance
from app.services.sessions import resolve_session

router = APIRouter()

DATA_PLANE_SECRET_HEADER = "x-data-plane-secret"
FORWARDED_URI_HEADER = "x-forwarded-uri"


def _instance_id_from_uri(uri: str | None) -> str | None:
    if not uri:
        return None
    parts = urlsplit(uri).path.split("/")
    if len(parts) < 3 or parts[1] != "i" or not parts[2]:
        return None
    return parts[2]


def _basic_auth_header(user: str, password: str) -> str:
    token = base64.b64encode(f"{user}:{password}".encode()).decode()
    return f"Basic {token}"


def _secret_matches(presented: str, configured: str) -> bool:
    # Vazio desativa o endpoint: sem segredo configurado ninguém é aprovado.
    if not configured:
        return False
    return hmac.compare_digest(presented.encode(), configured.encode())


@router.api_route(
    "/internal/data-plane/authorize",
    methods=["GET"],
    include_in_schema=False,  # contrato interno do plano de dados, não da API pública
)
def authorize(request: Request, db=Depends(get_db)) -> Response:
    settings: Settings = request.app.state.settings
    if not _secret_matches(
        request.headers.get(DATA_PLANE_SECRET_HEADER, ""), settings.data_plane_secret
    ):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="não autorizado")

    instance_id = _instance_id_from_uri(request.headers.get(FORWARDED_URI_HEADER))
    if instance_id is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="não encontrada")

    token = request.cookies.get(SESSION_COOKIE_NAME)
    user = resolve_session(db, token) if token is not None else None
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="não autenticado")

    try:
        row = get_owned_instance(db, instance_id, user.id)
    except NotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="não encontrada"
        ) from exc

    if row["state"] != "running":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="instância não está em execução"
        )

    request.app.state.activity_tracker.touch(instance_id)

    # Este cabeçalho é copiado pelo `copy_headers Authorization` do Caddy
    # para a requisição encaminhada; nunca é devolvido ao cliente.
    return Response(
        status_code=status.HTTP_200_OK,
        headers={"Authorization": _basic_auth_header(row["inner_user"], row["inner_password"])},
    )
